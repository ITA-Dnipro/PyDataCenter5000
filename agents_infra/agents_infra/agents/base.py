import abc
import copy
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

        if not isinstance(config, Config):
            raise TypeError(
                'Input server config must be either a dict or '
                'an instance of Config, not %s' % type(config)
            )

        # Base config from global defaults - make a copy to avoid shared state
        base_config = copy.deepcopy(self.config) or Config()

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

        Parameters:
            filename (str): Path to configuration file. Default is None.
            log_path (str): Path to where the log files will be stored.
                Default is None.

        Returns:
            ServerAgent: Child instance of ServerAgent.
        """
        config, tags = parse_config_file(filename)

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

    def send_request(
        self,
        method,
        url,
        payload=None,
        to_controller=True,
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
        fail_silently=True,
        headers=None
    ):
        """
        Universal HTTP request sender for Python 2.6.
        Supports GET, POST, PATCH via method override.
        """
        if to_controller:
            if not self.config.url:
                maybe_log_message(
                    "Couldn't send request to controller: URL not set",
                    logger=self.logger,
                )
                return

            base_api_url = urljoin(self.config.url, self.config.api_prefix)
            url = urljoin(base_api_url, url)

        headers = headers or {}

        if method.upper() == 'GET':
            headers.setdefault('Accept', 'application/json')
            data = None
        else:
            headers.setdefault('Content-Type', 'application/json')
            if not isinstance(payload, basestring):
                payload = json.dumps(payload)
            data = payload

        if api_key:
            headers['Authorization'] = '%s %s' % (
                self.config.auth_token_type, api_key
            )

        for attempt in range(1, max_retries + 1):
            try:
                maybe_log_message(
                    '[Attempt %d] Sending %s to %s' % (attempt, method, url),
                    logger=self.logger,
                    level=logging.INFO
                )

                request = urllib2.Request(url, data=data, headers=headers)
                # Override HTTP method
                request.get_method = lambda: method.upper()

                response = urllib2.urlopen(request, timeout=timeout)
                result = response.read()
                status_code = response.getcode()
                response.close()

                maybe_log_message(
                    '%s request status: %d' % (method, status_code),
                    logger=self.logger,
                    level=logging.INFO
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
                        'Retrying in %d seconds...' % (delay * attempt),
                        logger=self.logger,
                        level=logging.WARNING,
                    )
                    time.sleep(delay * attempt)
                elif not fail_silently:
                    raise RuntimeError(
                        '%s request failed after %d attempts' % (
                            method, max_retries
                        )
                    )

        maybe_log_message(
            'All %d attempts failed for %s %s' % (max_retries, method, url),
            logger=self.logger,
            level=logging.CRITICAL,
        )

    def get_data(self, url, **kwargs):
        return self.send_request('GET', url, **kwargs)

    def post_data(self, url, payload, **kwargs):
        return self.send_request('POST', url, payload=payload, **kwargs)

    def patch_data(self, url, payload, **kwargs):
        return self.send_request('PATCH', url, payload=payload, **kwargs)

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

    def handle_command_lifecycle(self, **kwargs):
        """
        Handle the command lifecycle by executing the command and
        posting the result to the controller.
        """
        command_history = self.execute_command(**kwargs)

        if command_history:
            try:
                patch_url = 'api/v1/commands/%s/' % command_history.id

                payload = {
                    'id': command_history.id,
                    'hostname': command_history.hostname,
                    'status': command_history.status.value,
                    'result': command_history.result,
                }
                self.patch_data(patch_url, payload)
            except RuntimeError as e:
                maybe_log_message(
                    'Failed to patch command result: %s' % str(e),
                    logger=self.logger,
                )
