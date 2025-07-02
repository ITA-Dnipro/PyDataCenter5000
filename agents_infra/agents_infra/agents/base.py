import abc
import datetime
import json
import logging
import logging.config
import platform
import socket
import time

import attr
import ConfigParser
import pkg_resources
import Queue
import urllib2
from urlparse import urljoin

from ..command import CommandHistory, CommandStatus, dispatch_command
from ..exceptions import BadProcessReturnCode
from ..utils import LOG_CONFIG_PATH, maybe_log_message
from ..utils.configtools import get_config_option, parse_csv_list
from ..utils.helpers import is_process_active, restart_service
from ..utils.sysinfo import get_ip_from_interface, get_linux_uptime

PROTOCOLS = ('tcp', 'udp')


@attr.s
class Config(object):
    """Helper class used to validate self.config in ServerAgent."""
    name = attr.ib(validator=attr.validators.instance_of(str))
    api_prefix = attr.ib(validator=attr.validators.instance_of(str))
    url = attr.ib(validator=attr.validators.instance_of(str))
    critical_processes = attr.ib(validator=attr.validators.instance_of(list))
    whitelist_commands = attr.ib(validator=attr.validators.instance_of(list))
    port = attr.ib(validator=attr.validators.instance_of(int))

    auth_token_type = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    interface = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def get(self, key, default=None):
        return getattr(self, key, default)

    def update(self, updates):
        """
        Update existing config with new values.

        Special handling for:
        - whitelist_commands: extend without duplicates
        - critical_processes: extend without duplicates
        """
        if isinstance(updates, Config):
            updates = attr.asdict(updates)

        for key, value in updates.items():
            if value is None:
                continue

            if key in ('whitelist_commands', 'critical_processes'):
                original = getattr(self, key, [])
                if not isinstance(value, list):
                    raise TypeError(
                        'Expected list for %s, got %s' % (key, type(value))
                    )
                merged = original + [v for v in value if v not in original]
                setattr(self, key, merged)
            elif hasattr(self, key):
                setattr(self, key, value)
            else:
                # For unknown keys, optionally skip or log
                # Maybe extend later
                pass


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """

    __metaclass__ = abc.ABCMeta

    defaults = {
        'name': 'default',
        'api_prefix': 'api/',
        'url': '',
        'critical_processes': [],
        'whitelist_commands': [],
        'port': 0,
        'auth_token_type': None,
        'interface': None,
    }

    # Global config parsed once at import-level (__init__.py)
    config = None  # Will hold default/global config

    def __init__(
        self,
        server_name=None,
        protocol=None,
        command_queue_size=0,
        config=None
    ):
        self.server_name = server_name

        # If not provided, use class-level default config
        base_config = ServerAgent.config or {}

        if isinstance(base_config, dict):
            merged = dict(ServerAgent.defaults)
            merged.update(base_config)
            base_config = Config(**merged)

        if config is None:
            config = {}

        if isinstance(config, dict):
            config = Config(**config)

        if not isinstance(config, Config):
            raise TypeError(
                "Expected 'config' to be instance of Config or dict"
            )

        # Merge global + instance config
        base_config.update(attr.asdict(config))
        self.config = base_config

        if protocol is not None:
            self.protocol = protocol

        # Init server metadata to prevent AttributeError
        self.os_type = self.hostname = self.ip = None
        self.uptime = self.timestamp = None

        # Thread-safe queue to store pending commands.
        self.command_queue = Queue.Queue(maxsize=max(command_queue_size, 0))

    @classmethod
    def from_config_file(cls, filename=None, log_path=None):
        """
        Create an agent from configuration file.
        Merges global config (ServerAgent.config) with local config.ini.
        """

        base_config = cls.config or {}

        if isinstance(base_config, Config):
            config_obj = type(base_config)(**attr.asdict(base_config))
        elif isinstance(base_config, dict):
            merged = dict(ServerAgent.defaults)
            merged.update(base_config)
            config_obj = Config(**merged)
        else:
            raise TypeError('Expected class-level config to be Config or dict')

        local_config = cls._parse_config_file(filename)
        config_obj.update(local_config)

        agent = cls(
            server_name=config_obj.name,
            config=config_obj,
        )

        agent.setup_logging(log_path)
        return agent

    def setup_logging(self, log_path=None):
        """
        Setup agent's logger based on its server_name.

        Parameters:
            log_path (PathLike, optional): Path to where logs will be
                stored.
        """
        log_path = (
            log_path or pkg_resources.
            resource_filename(
                self.__class__.__module__, 'logs/%s.log' % self.server_name
            )
        )

        logging.config.fileConfig(
            LOG_CONFIG_PATH,
            defaults={
                'agent_name': self.server_name,
                'log_path': log_path
            },
        )

    @property
    def logger(self):
        if not self.server_name:
            raise ValueError('Must assign a valid server name to use logger')

        return logging.getLogger(self.server_name)

    @property
    def protocol(self):
        return getattr(self, '_protocol', None)

    @protocol.setter
    def protocol(self, value):
        if not isinstance(value, (str, unicode)):
            raise TypeError('Protocol must be a string, not %s' % type(value))

        value = value.lower()

        if value not in PROTOCOLS:
            raise ValueError('Unknown protocol value %s' % value)

        self._protocol = value

    @staticmethod
    def _parse_config_file(filename=None):
        """
        Load and parse agent-specific config file.
        Merges config.ini with global_config using Config.update().
        Returns a Config instance.
        """
        config_files = [
            filename or pkg_resources.resource_filename(__name__, 'config.ini')
        ]

        parser = ConfigParser.ConfigParser()
        parser.read(config_files)

        type_casts = {
            'port': int,
            'critical_processes': parse_csv_list,
            'whitelist_commands': parse_csv_list,
        }

        base = ServerAgent.config or {}

        if isinstance(base, Config):
            config_obj = type(base)(**attr.asdict(base))
        elif isinstance(base, dict):
            merged = dict(ServerAgent.defaults)
            merged.update(base)
            config_obj = Config(**merged)
        else:
            raise TypeError("Expected 'base' to be Config or dict")

        temp_dict = {}

        for section in parser.sections():
            for key, value in parser.items(section):
                caster = type_casts.get(key, str)
                try:
                    parsed = caster(value) or None
                    temp_dict[key] = parsed
                except Exception:
                    continue  # Skip incorrect data

        config_obj.update(temp_dict)
        return config_obj

    def collect_server_metadata(self):
        """
        Attempt setting server metadata such as the hostname, IP address,
        uptime, and timestamp.
        """
        system = platform.system()
        if not system:
            maybe_log_message('Could not deduce OS type', logger=self.logger)

        self.os_type = system.lower() or 'unknown'

        try:
            self.hostname = socket.gethostname()
        except socket.error as e:
            self.hostname = 'unknown'

            maybe_log_message(
                'Could not get hostname: %s' % str(e), logger=self.logger
            )

        self.ip = None

        if self.config.get('interface'):
            try:
                self.ip = get_ip_from_interface(self.config.get('interface'))
            except (KeyError, AttributeError) as e:
                maybe_log_message(
                    (
                        'Could not deduce IP address from interface '
                        '%s: %s' % (self.config.get('interface'), str(e))
                    ),
                    logger=self.logger,
                )

        if not self.ip and self.hostname != 'UNKNOWN':
            try:
                self.ip = socket.gethostbyname(self.hostname)
            except (socket.gaierror, socket.error) as e:
                maybe_log_message(
                    'Could not deduce IP address from hostname: %s' % str(e),
                    self.logger,
                )

        self.uptime = -1

        if 'linux' in self.os_type:
            self.uptime = get_linux_uptime()

        if self.uptime < 0:
            maybe_log_message(
                "Could not get system's uptime", logger=self.logger
            )

        self.timestamp = datetime.datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        data = self.status_to_dict()
        for k, v in data.items():
            self.logger.info(u'%s: %s' % (k, v))

    def is_port_open(self, timeout=2, payload=None, packet_size=0):
        """
        Check if the port is open.

        Returns:
            bool: Port status.

        Raises:
            ValueError: If the port not assigned a valid number.
        """
        if self.config.get('port') == -1:
            raise ValueError(
                'Port not set: server agent must assign a valid port number'
            )

        if not self.ip:
            return False

        if not self.protocol:
            raise ValueError(
                'Protocol not set: server agent must set a valid transfer '
                'protocol (TCP or UDP)'
            )

        s = socket.socket(
            socket.AF_INET,
            (
                socket.SOCK_STREAM if self.protocol == 'tcp'
                else socket.SOCK_DGRAM
            ),
        )
        s.settimeout(timeout)

        try:
            if self.protocol == 'tcp':
                s.connect((self.ip, self.config.get('port')))
            else:
                s.sendto(payload or b'', (self.ip, self.config.get('port')))

            if packet_size > 0:
                data, _ = s.recvfrom(packet_size)
                if len(data) != packet_size:
                    maybe_log_message(
                        (
                            'UDP response size mismatch: expected '
                            '%d bytes, got %d bytes' % (packet_size, len(data))
                        ),
                        logger=self.logger,
                    )

                    return False

            return True
        except (socket.error, socket.timeout) as e:
            maybe_log_message(
                'Port check failed due to error: %s' % str(e),
                logger=self.logger,
            )

            return False
        finally:
            s.close()

    def _are_all_critical_processes_active(self, restart=False):
        inactive_processes = 0

        try:
            for proc in self.config.get('critical_processes'):
                is_active = is_process_active(proc)
                if not is_active:
                    inactive_processes += 1
                    maybe_log_message(
                        '%s process inactive' % proc,
                        self.logger
                    )
                    if restart:
                        restart_service(
                            self.logger, proc
                        )

            return inactive_processes == 0

        except OSError as e:
            maybe_log_message(
                'Critical processes check failed: %s' % e,
                logger=self.logger,
                exc_info=True
                )
            return False

        except Exception as e:
            maybe_log_message(
                'Critical processes check failed: %s' % e,
                self.logger,
                exc_info=True
            )
            return False

    @abc.abstractmethod
    def is_service_healthy(self):
        """
        Check if the specific service (SMTP, DNS, etc.) is running and
        healthy.
        """
        return self._are_all_critical_processes_active()

    def status_to_dict(self):
        return {
            'os': self.os_type,
            'hostname': self.hostname,
            'ip': self.ip,
            'server_name': self.server_name,
            'uptime': self.uptime,
            'timestamp': self.timestamp,
            'healthy': self.is_service_healthy(),
        }

    def post_data(
        self,
        url,
        payload,
        to_controller=True,
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
        fail_silently=True,
        **kwargs
    ):
        """
        Sends a POST request with JSON data to the specified URL with
        retry logic. Retries up to `max_retries` times with `delay`
        seconds between attempts. Logs all attempts and failures.

        Parameters:
            url (str): Endpoint URL or, for `to_controller=True`,
                suffix of controller's endpoint, i.e.,
                <controller_url>/<api_prefix>/url.
            payload (Any): Data to send via POST request. If not a string,
                JSON serialization will be attempted.
            api_key (str, optiona): API key for authorization. Default
                is None.
            max_retries (int, optional): Maximum number of retry attempts.
                Default is 3.
            delay (int, optional): Delay (in seconds) between retries.
                Default is 5.
            timeout (int, optional): POST request timeout (in seconds).
                Default is 5.
            to_controller (bool, optional): Whether data is to be sent
                to controller. Default is False.
            **kwargs: Key-value pairs to be appended to the header.
        """
        if to_controller:
            if not self.config.url:
                maybe_log_message(
                    (
                        "Couldn't send POST request to controller: "
                        'controller URL is not set'
                    ),
                    logger=self.logger,
                )
                return

            base_api_url = urljoin(self.config.url, self.config.api_prefix)
            url = urljoin(base_api_url, url)

        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers.update(
                {'Authorization': '%s %s' % (
                    self.config.auth_token_type, api_key
                )}
            )
        if kwargs:
            headers.update(kwargs)

        if not isinstance(payload, str):
            payload = json.dumps(payload)

        for attempt in range(1, max_retries + 1):
            try:
                maybe_log_message(
                    '[Attempt %d] Sending data to %s' % (attempt, url),
                    logger=self.logger,
                    level=logging.INFO
                )

                request = urllib2.Request(url, data=payload, headers=headers)

                response = urllib2.urlopen(request, timeout=timeout)
                result = response.read()
                status_code = response.getcode()

                maybe_log_message(
                    'POST request status: %d' % status_code,
                    logger=self.logger,
                    level=logging.INFO
                )

                response.close()

                maybe_log_message(
                    'POST request succeeded on attempt %d: %s' % (
                        attempt, result
                    ),
                    logger=self.logger,
                    level=logging.INFO,
                )

                return result
            except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
                maybe_log_message(
                    'Attempt %d failed: %s' % (attempt, e),
                    logger=self.logger,
                    level=logging.ERROR,
                )

                if attempt < max_retries:
                    maybe_log_message(
                        'Retrying in %d seconds...' % delay,
                        logger=self.logger,
                        level=logging.WARNING,
                    )
                    time.sleep(delay * attempt)
                else:
                    maybe_log_message(
                        'All %d attempts failed. Data not sent. '
                        'Last error: %s' % (max_retries, e),
                        logger=self.logger,
                        level=logging.CRITICAL,
                    )

                    if not fail_silently:
                        raise RuntimeError(
                            'POST failed after %d attempts' % max_retries
                        )

    def get_data(
        self,
        url,
        to_controller=True,
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
        fail_silently=True,
        **kwargs
    ):
        """
        Sends a GET request to the specified URL with retry logic.
        Retries up to `max_retries` times with `delay` seconds between
        attempts. Logs all attempts and failures.

        Parameters:
            url (str): Endpoint URL or, if `to_controller=True`, suffix
                of controller's endpoint, i.e.,
                <controller_url>/<api_prefix>/url.
            to_controller (bool, optional): Whether URL is relative to
                controller. Default is True.
            api_key (str, optional): API key for authorization. Default None.
            max_retries (int, optional): Maximum number of retry attempts.
            delay (int, optional): Delay between retries in seconds.
            timeout (int, optional): Timeout for GET request.
            fail_silently (bool, optional): Whether to suppress exceptions
                after final failure.
            **kwargs: Optional headers to include in the request.

        Returns:
            str: The response content on success.

        Raises:
            RuntimeError: If all attempts fail and `fail_silently` is False.
        """
        if to_controller:
            if not self.config.url:
                maybe_log_message(
                    (
                        "Couldn't send GET request to controller: "
                        'controller URL is not set'
                    ),
                    logger=self.logger,
                )
                return

            base_api_url = urljoin(self.config.url, self.config.api_prefix)
            url = urljoin(base_api_url, url)

        headers = {'Accept': 'application/json'}
        if api_key:
            headers['Authorization'] = '%s %s' % (
                self.config.auth_token_type, api_key
            )
        if kwargs:
            headers.update(kwargs)

        for attempt in range(1, max_retries + 1):
            try:
                maybe_log_message(
                    '[Attempt %d] Sending GET request to %s' % (attempt, url),
                    logger=self.logger,
                    level=logging.INFO
                )

                request = urllib2.Request(url, headers=headers)
                response = urllib2.urlopen(request, timeout=timeout)
                result = response.read()
                status_code = response.getcode()
                response.close()

                maybe_log_message(
                    'GET request status: %d' % status_code,
                    logger=self.logger,
                    level=logging.INFO
                )

                maybe_log_message(
                    'GET request succeeded on attempt %d: %s' % (
                        attempt, result
                    ),
                    logger=self.logger,
                    level=logging.INFO,
                )

                return result

            except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
                maybe_log_message(
                    'Attempt %d failed: %s' % (attempt, e),
                    logger=self.logger,
                    level=logging.ERROR,
                )

                if attempt < max_retries:
                    maybe_log_message(
                        'Retrying in %d seconds...' % delay,
                        logger=self.logger,
                        level=logging.WARNING,
                    )
                    time.sleep(delay * attempt)
                else:
                    maybe_log_message(
                        'All %d attempts failed. Data not received. '
                        'Last error: %s' % (max_retries, e),
                        logger=self.logger,
                        level=logging.CRITICAL,
                    )

                    if not fail_silently:
                        raise RuntimeError(
                            'GET failed after %d attempts' % max_retries
                        )

    def maybe_add_command_to_queue(self, data, block=False, timeout=None):
        """
        Add command to queue if it passes field validation and if
        whitelisted by the server.
        """
        if not isinstance(data, dict):
            maybe_log_message(
                'Expected data as a dict, got %s' % type(data),
                logger=self.logger,
            )

            return

        try:
            command_history = CommandHistory.from_dict(data)
        except (TypeError, ValueError) as e:
            maybe_log_message(
                'Command validation failed due to error: %s' % str(e),
                logger=self.logger,
            )

            return

        if command_history.command.tag in self.config.whitelist_commands:
            try:
                self.command_queue.put(
                    command_history, block=block, timeout=timeout
                )
            except Queue.Full:
                maybe_log_message(
                    'Queue is full - could not append command',
                    logger=self.logger,
                )
        else:
            maybe_log_message(
                'Command %s not permitted' % command_history.command.tag,
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.WARNING,
            )

    def get_command_from_queue(self, block=False, timeout=None):
        try:
            return self.command_queue.get(block=block, timeout=timeout)
        except Queue.Empty:
            maybe_log_message(
                'Queue is empty - could not retrieve command',
                logger=self.logger,
            )

    def execute_command(self, **kwargs):
        """
        Pull command from the queue and delegate execution to
        CommandDispatcher.
        """
        command_history = self.get_command_from_queue(**kwargs)

        if command_history:
            try:
                result = dispatch_command(command_history.command, self)

                command_history.status = CommandStatus.DONE
            except BadProcessReturnCode as e:
                maybe_log_message(
                    'Command failed due to error: %s.\nstderr: %s' % (
                        str(e), result
                    ),
                    logger=self.logger,
                )

                command_history.status = CommandStatus.FAILED

            command_history.result = result

            return command_history
