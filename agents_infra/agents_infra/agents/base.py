import abc
import copy
import datetime
import json
import logging
import logging.config
import platform
import socket
import time

import ConfigParser
import pkg_resources
import Queue
import urllib2
from urlparse import urljoin

from ..command import CommandHistory, CommandStatus, dispatch_command
from ..exceptions import BadProcessReturnCode
from ..utils import LOG_CONFIG_PATH, maybe_log_message
from ..utils.configtools import Config, parse_config_file, write_config_options
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

    def _parse_config_file(self, filename=None):
        """Parse server's config file using ConfigParser."""
        filename = filename or pkg_resources.resource_filename(
            self.__class__.__module__, 'config.ini'
        )

        config = ConfigParser.ConfigParser()
        config.read(filename)

        if config.sections():
            self.server_name = get_config_option(
                config,
                'server',
                'name',
                default=self.server_name,
                logger=self.logger,
            )

            self.port = get_config_option(
                config,
                'server',
                'port',
                default=self.port,
                logger=self.logger,
                cast=int,
            )

            self.processes = get_config_option(
                config,
                'server',
                'processes',
                default=self.processes,
                logger=self.logger,
                cast=parse_csv_list,
            )

            # Append server-specific critical_processes
            critical_processes = get_config_option(
                config,
                'server',
                'critical_processes',
                logger=self.logger,
                cast=parse_csv_list,
            )

            # Extend avoiding duplicates
            if critical_processes:
                self.critical_processes.extend(
                    proc for proc in critical_processes
                    if proc not in self.critical_processes
                )

            self.interface = get_config_option(
                config, 'server', 'interface', logger=self.logger
            )

            whitelist_commands = get_config_option(
                config,
                'controller',
                'whitelist_commands',
                logger=self.logger,
                cast=parse_csv_list,
            )
            # Add commands to the list of globally allowed commands.
            if whitelist_commands:
                self.whitelist_commands.extend(
                    cmd for cmd in whitelist_commands
                    if cmd not in self.whitelist_commands
                )

            # Read tags from the [server] section
            tags = {}
            for tag_key in ['env', 'role', 'region']:
                tag_value = get_config_option(
                    config,
                    'server',
                    tag_key,
                    logger=self.logger,
                )
                if tag_value and tag_value.strip():
                    tags[tag_key] = tag_value.strip().lower()
            if tags:
                self.tags = tags

    def send_log_to_controller(self, level, message, context=None):
        """
        Sends a log message to the controller's /logs/ endpoint.
        Parameters:
            level (str): Log level (e.g. "INFO", "ERROR", etc.).
            message (str): Log message.
            context (dict, optional): Additional log context.
        """
        if not self.config.post_agent_log_url:
            raise ValueError('Post agent log controller URL is not set')

        log_data = {
            'agent_name': self.server_name,
            'level': level,
            'message': message,
            'timestamp': self.timestamp,
            'context': context or {},
        }

        self.post_data(
            self.config.post_agent_log_url,
            payload=log_data,
            to_controller=True
        )

    def log_with_controller(
             self,
             message,
             level=logging.INFO,
             context=None,
             fallback_logger=None,
             exc_info=None,
             **kwargs
    ):
        """
        Logs a message locally and optionally sends it to the controller.
        Parameters:
            message (str): The log message.
            level (int): Logging level.
            context (dict): Optional log context.
            exc_info (bool or Exception): Exception info for traceback logging.
        """
        maybe_log_message(
            message,
            logger=self.logger,
            fallback_logger=fallback_logger,
            level=level,
            exc_info=exc_info,
            **kwargs
        )

        if getattr(self, 'send_logs_to_controller', False):
            try:
                self.send_log_to_controller(
                    level=logging.getLevelName(level),
                    message=message,
                    context=context
                )
            except Exception as e:
                maybe_log_message(
                    'Failed to send log to controller: %s' % str(e),
                    logger=self.logger,
                    level=logging.ERROR,
                )

    def collect_server_metadata(self):
        """
        Attempt setting server metadata such as the hostname, IP address,
        uptime, and timestamp.
        """
        system = platform.system()
        if not system:
            self.log_with_controller(
                'Could not deduce OS type', level=logging.WARNING
            )

        self.os_type = system.lower() or 'unknown'

        try:
            self.hostname = socket.gethostname()
        except socket.error as e:
            self.hostname = 'unknown'
            self.log_with_controller(
                'Could not get hostname: %s' % str(e), level=logging.WARNING
            )

        self.ip = None

        if self.config.interface:
            try:
                self.ip = get_ip_from_interface(self.config.interface)
            except (KeyError, AttributeError) as e:
                self.log_with_controller(
                    (
                        'Could not deduce IP address from interface '
                        '%s: %s' % (self.config.interface, str(e))
                    ),
                    level=logging.WARNING,
                )

        if not self.ip and self.hostname != 'UNKNOWN':
            try:
                self.ip = socket.gethostbyname(self.hostname)
            except (socket.gaierror, socket.error) as e:
                self.log_with_controller(
                    'Could not deduce IP address from hostname: %s' % str(e),
                    level=logging.WARNING,
                )

        self.uptime = -1

        if 'linux' in self.os_type:
            self.uptime = get_linux_uptime()

        if self.uptime < 0:
            self.log_with_controller(
                "Could not get system's uptime", level=logging.WARNING
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
            self.log_with_controller(
                'Critical process check failed: %s' % e,
                level=logging.ERROR,
                exc_info=True,
            )

            return False

        except Exception as e:
            self.log_with_controller(
                'Critical processes check failed: %s' % e,
                level=logging.ERROR,
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
            if not self.config.current_controller or not url:
                maybe_log_message(
                    (
                        "Couldn't send POST request to controller: "
                        'controller URL is not set'
                    ),
                    logger=self.logger,
                )
                return

            base_api_url = urljoin(
                self.config.current_controller,
                self.config.api_prefix
            )
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
            if not self.config.current_controller or not url:
                maybe_log_message(
                    (
                        "Couldn't send GET request to controller: "
                        'controller URL is not set'
                    ),
                    logger=self.logger,
                )
                return

            base_api_url = urljoin(
                self.config.current_controller,
                self.config.api_prefix
            )
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

                self.log_with_controller(
                    'GET request status: %d' % status_code,
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
            self.log_with_controller(
                'Expected data as a dict, got %s' % type(data),
                level=logging.WARNING,
            )
            return

        try:
            command_history = CommandHistory.from_dict(data)
        except (TypeError, ValueError) as e:
            self.log_with_controller(
                'Command validation failed due to error: %s' % str(e),
                level=logging.WARNING,
            )

            return

        if command_history.command.tag in self.config.whitelist_commands:
            try:
                self.command_queue.put(
                    command_history, block=block, timeout=timeout
                )
            except Queue.Full:
                self.log_with_controller(
                    'Queue is full - could not append command',
                    level=logging.WARNING,
                )
        else:
            self.log_with_controller(
                'Command %s not permitted' % command_history.command.tag,
                level=logging.WARNING,
            )

    def get_command_from_queue(self, block=False, timeout=None):
        try:
            return self.command_queue.get(block=block, timeout=timeout)
        except Queue.Empty:
            self.log_with_controller(
                'Queue is empty - could not retrieve command',
                level=logging.INFO,
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
                self.log_with_controller(
                    'Command failed due to error: %s.\nstderr: %s' % (
                        str(e), result
                    ),
                    level=logging.ERROR,
                )

                command_history.status = CommandStatus.FAILED

            command_history.result = result

            return command_history

    def set_tags(self, tags):
        """
        Updates tags in the config file and reloads the agent's configuration.
        """
        config_path = getattr(self.config, 'path', None)
        if not config_path:
            maybe_log_message(
                'Cannot set tags: config file path is not defined '
                'for this agent.',
                logger=self.logger,
                level=logging.ERROR
            )
            return

        if not isinstance(tags, dict):
            maybe_log_message(
                "Command 'set_tags' failed: expected a dictionary of tags.",
                logger=self.logger,
                level=logging.ERROR
            )
            return

        if not tags:
            maybe_log_message(
                "Command 'set_tags' received empty tags. No action taken.",
                logger=self.logger,
                level=logging.WARNING
            )
            return

        allowed_keys = set(['env', 'role', 'region'])
        for key, value in tags.items():
            if key not in allowed_keys:
                maybe_log_message(
                    "Command 'set_tags' failed: invalid tag key '%s'." % key,
                    logger=self.logger,
                    level=logging.ERROR
                )
                return

            if value is not None and not isinstance(value, basestring):
                maybe_log_message(
                    "Command 'set_tags' failed: "
                    "value for tag '%s' must be a string or None." % key,
                    logger=self.logger,
                    level=logging.ERROR
                )
                return

        try:
            maybe_log_message(
                'Received set_tags command. Applying new tags: %s' % tags,
                logger=self.logger,
                level=logging.INFO
            )
            write_config_options(config_path, 'server', tags)

            maybe_log_message(
                'Reloading configuration from %s' % config_path,
                logger=self.logger,
                level=logging.INFO
            )
            new_config, new_tags = parse_config_file(config_path)
            self.config = new_config
            self.tags = new_tags

            maybe_log_message(
                'Tags updated successfully. '
                'Current tags are now: %s' % self.tags,
                logger=self.logger,
                level=logging.INFO
            )

        except (IOError, OSError, ConfigParser.Error) as e:
            maybe_log_message(
                'Failed to execute set_tags command: %s' % e,
                logger=self.logger,
                level=logging.ERROR,
                exc_info=True
            )
