import abc
import datetime
import json
import logging
import logging.config
import platform
import socket
import time

import pkg_resources
import Queue
import urllib2
from urlparse import urljoin

from ..command import CommandHistory, CommandStatus, dispatch_command
from ..exceptions import BadProcessReturnCode
from ..utils import LOG_CONFIG_PATH, maybe_log_message
from ..utils.configtools import Config, parse_config_file
from ..utils.helpers import is_process_active, restart_service
from ..utils.sysinfo import get_ip_from_interface, get_linux_uptime

PROTOCOLS = ('tcp', 'udp')


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """

    __metaclass__ = abc.ABCMeta

    # Global config parsed once at import-level (__init__.py)
    config = None  # Will hold default/global config

    def __init__(self, protocol=None, command_queue_size=0, config=None):
        self.health_thread = None

        # Normalize user config
        if config is None:
            config = Config()
        elif isinstance(config, dict):
            config = Config.from_dict(config)
        elif not isinstance(config, Config):
            raise TypeError(
                'Input server config must be either a dict or '
                'an instance of Config, not %s' % type(config)
            )

        # Base config from global defaults - make a copy to avoid shared state
        if isinstance(ServerAgent.config, Config):
            base_config = Config.from_dict(ServerAgent.config.__dict__)
        else:
            base_config = Config.from_dict(ServerAgent.config or {})

        # Merge user config into base config (without mutating the original)
        base_config.update(config)
        self.config = base_config

        # Optional protocol override
        if protocol is not None:
            self.protocol = protocol

        # Init server metadata to prevent AttributeError
        self.os_type = self.hostname = self.ip = None
        self.uptime = self.timestamp = None

        # Thread-safe queue to store pending commands
        self.command_queue = Queue.Queue(maxsize=max(command_queue_size, 0))

        # Initialize tags
        self.tags = {}

    @classmethod
    def from_config_file(cls, filename=None, log_path=None):
        """
        Create an agent from configuration file.
        Merges global config (ServerAgent.config) with local config.ini.
        """
        base_config = ServerAgent.config or Config()
        config, tags = parse_config_file(filename, base_config=base_config)
        agent = cls(config=config)
        agent.tags = tags
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
                self.__class__.__module__, 'logs/%s.log' % self.config.name
            )
        )

        logging.config.fileConfig(
            LOG_CONFIG_PATH,
            defaults={
                'agent_name': self.config.name,
                'log_path': log_path
            },
        )

    @property
    def logger(self):
        if not self.config.name:
            raise ValueError('Must assign a valid server name to use logger')

        return logging.getLogger(self.config.name)

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

        if self.config.interface:
            try:
                self.ip = get_ip_from_interface(self.config.interface)
            except (KeyError, AttributeError) as e:
                maybe_log_message(
                    (
                        'Could not deduce IP address from interface '
                        '%s: %s' % (self.config.interface, str(e))
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

    def _are_all_critical_processes_active(self, restart=False):
        inactive_processes = 0

        try:
            for proc in self.config.critical_processes:
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
        status_data = {
            'os': self.os_type,
            'hostname': self.hostname,
            'ip': self.ip,
            'server_name': self.config.name,
            'uptime': self.uptime,
            'timestamp': self.timestamp,
            'healthy': self.is_service_healthy(),
        }
        if self.tags:
            status_data['tags'] = self.tags

        return status_data

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
        from_controller=True,
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
        if from_controller:
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
