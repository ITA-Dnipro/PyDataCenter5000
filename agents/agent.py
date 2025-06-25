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
from dateutil import parser
from urlparse import urljoin

from .utils.configtools import get_config_option, parse_csv_list
from .utils.helpers import is_process_active, restart_service
from .utils.logtools import maybe_log_message
from .utils.sysinfo import (generate_report, get_ip_from_interface,
                            get_linux_uptime)

log_config_path = pkg_resources.resource_filename(
    'agents.utils.logtools', 'logconfig.ini'
)

PROTOCOLS = ('tcp', 'udp')


@attr.s
class CommandHistory(object):
    """Helper class used to validate command fields."""
    command = attr.ib(validator=attr.validators.instance_of(basestring))
    hostname = attr.ib(validator=attr.validators.instance_of(basestring))
    status = attr.ib(validator=attr.validators.instance_of(basestring))
    timestamp = attr.ib(
        validator=lambda instance, attribute, value: parser.parse(value)
    )
    result = attr.ib(default=None)
    id = attr.ib(default=None)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """

    __metaclass__ = abc.ABCMeta

    controller_url = None
    api_prefix = 'api/'
    auth_token_type = 'Bearer'
    whitelist_commands = None
    critical_processes = None

    def __init__(
        self,
        server_name=None,
        port=None,
        critical_processes=None,
        interface=None,
        protocol=None,
        whitelist_commands=None,
    ):
        self.server_name = server_name
        self.port = port if port is not None else self.port
        self.interface = interface

        if protocol is not None:
            self.protocol = protocol

        self.whitelist_commands = self.whitelist_commands or []
        if whitelist_commands is not None:
            self.whitelist_commands.extend(whitelist_commands)

        # Init config atribute(to save data from config file)
        self.config = None

        # Extend the list of global critical processes with those that
        # are server-specific.
        self.critical_processes = self.critical_processes or []
        if critical_processes is not None:
            self.critical_processes.extend(critical_processes)

        # Init server metadata to prevent AttributeError and to indicate
        # to user that collect_server_metadata hasn't been called.
        self.os_type = self.hostname = self.ip = None
        self.uptime = self.timestamp = None

        # Initialize thread-safe command queue
        self.queue = Queue.Queue()

    @classmethod
    def from_config_file(cls, filename=None, log_path=None):
        """
        Create an agent from a configuration (.ini) file.

        Parameters:
            filename (str): Path to configuration file. Default is None.
            log_path (str): Path to where the log files will be stored.
                Default is None.

        Returns:
            ServerAgent: Child instance of ServerAgent.
        """
        agent = cls()

        agent._parse_config_file(filename)
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
            log_path or pkg_resources.resource_filename(
                self.__class__.__module__, 'logs/%s.log' % self.server_name
            )
        )

        logging.config.fileConfig(
            log_config_path,
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
    def fallback_logger(self):
        return logging.getLogger(
            '_'.join([self.server_name, 'fallback'])
        )

    @property
    def port(self):
        return getattr(self, '_port', -1)

    @port.setter
    def port(self, value):
        if not isinstance(value, int):
            raise TypeError('Port number must be an integer')
        self._port = value

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
                fallback_logger=self.fallback_logger,
            )

            self.port = get_config_option(
                config,
                'server',
                'port',
                default=self.port,
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                cast=int,
            )

            # Append server-specific critical_processes
            critical_processes = get_config_option(
                config,
                'server',
                'critical_processes',
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                cast=parse_csv_list,
            )
            # Extend, avoiding duplicates
            if critical_processes:
                self.critical_processes.extend(
                    proc for proc in critical_processes
                    if proc not in self.critical_processes
                )

            self.interface = get_config_option(
                config,
                'server',
                'interface',
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )

            whitelist_commands = get_config_option(
                config,
                'controller',
                'whitelist_commands',
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                cast=parse_csv_list,
            )
            # Add commands to the list of globally allowed commands.
            if whitelist_commands:
                self.whitelist_commands.extend(
                    cmd for cmd in whitelist_commands
                    if cmd not in self.whitelist_commands
                )

    def collect_server_metadata(self):
        """
        Attempt setting server metadata such as the hostname, IP address,
        uptime, and timestamp.
        """
        system = platform.system()
        if not system:
            maybe_log_message(
                'Could not deduce OS type', self.logger, self.fallback_logger
            )

        self.os_type = system.lower() or 'unknown'

        try:
            self.hostname = socket.gethostname()
        except socket.error as e:
            self.hostname = 'unknown'

            maybe_log_message(
                'Could not get hostname: %s' % str(e),
                self.logger,
                fallback_logger=self.fallback_logger,
            )

        self.ip = None

        if self.interface:
            try:
                self.ip = get_ip_from_interface(self.interface)
            except (KeyError, AttributeError) as e:
                maybe_log_message(
                    (
                        'Could not deduce IP address from interface '
                        '%s: %s' % (self.interface, str(e))
                    ),
                    self.logger,
                    fallback_logger=self.fallback_logger,
                )

        if not self.ip and self.hostname != 'UNKNOWN':
            try:
                self.ip = socket.gethostbyname(self.hostname)
            except (socket.gaierror, socket.error) as e:
                maybe_log_message(
                    'Could not deduce IP address from hostname: %s' % str(e),
                    self.logger,
                    fallback_logger=self.fallback_logger,
                )

        self.uptime = -1

        if 'linux' in self.os_type:
            self.uptime = get_linux_uptime()

        if self.uptime < 0:
            maybe_log_message(
                "Could not get system's uptime",
                self.logger,
                fallback_logger=self.fallback_logger,
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
        if self.port == -1:
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
                s.connect((self.ip, self.port))
            else:
                s.sendto(payload or b'', (self.ip, self.port))

            if packet_size > 0:
                data, _ = s.recvfrom(packet_size)
                if len(data) != packet_size:
                    maybe_log_message(
                        (
                            'UDP response size mismatch: expected '
                            '%d bytes, got %d bytes' % (packet_size, len(data))
                        ),
                        logger=self.logger,
                        fallback_logger=self.fallback_logger,
                    )

                    return False

            return True
        except (socket.error, socket.timeout) as e:
            maybe_log_message(
                'Port check failed due to error: %s' % str(e),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )

            return False
        finally:
            s.close()

    def _are_all_critical_processes_active(self, restart=False):
        inactive_processes = 0

        try:
            for proc in self.critical_processes:
                is_active = is_process_active(proc)
                if not is_active:
                    inactive_processes += 1
                    maybe_log_message(
                        '%s process inactive' % proc,
                        self.logger,
                        fallback_logger=self.fallback_logger,
                        exc_info=True
                    )
                    if restart:
                        restart_service(
                            self.logger, self.fallback_logger, proc
                        )

            return inactive_processes == 0

        except OSError as e:
            maybe_log_message(
                'Critical processes check failed: %s' % e,
                self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True
                )
            return False

        except Exception as e:
            maybe_log_message(
                'Critical processes check failed: %s' % e,
                self.logger,
                fallback_logger=self.fallback_logger,
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
        self, url, data, api_key=None, max_retries=3, delay=5, timeout=5
    ):
        """
        Sends a POST request with JSON data to the specified URL
        with retry logic. Retries up to `max_retries` times with `delay`
        seconds between attempts. Logs all attempts and failures.
        """
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers.update(
                {'Authorization': '%s %s' % (self.auth_token_type, api_key)}
            )
        payload = json.dumps(data).encode('utf-8')

        for attempt in range(1, max_retries + 1):
            try:
                maybe_log_message(
                    '[Attempt %d] Sending data to %s' % (attempt, url),
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO
                )

                request = urllib2.Request(url, data=payload, headers=headers)

                response = urllib2.urlopen(request, timeout=timeout)
                result = response.read()
                status_code = response.getcode()

                maybe_log_message(
                    'POST request status: %d' % status_code,
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO
                )

                response.close()

                maybe_log_message(
                    'Success on attempt %d: %s' % (attempt, result),
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO
                )

                return result
            except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
                maybe_log_message(
                    'Attempt %d failed: %s' % (attempt, e),
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.ERROR
                )

                if attempt < max_retries:
                    maybe_log_message(
                        'Retrying in %d seconds...' % delay,
                        logger=self.logger,
                        fallback_logger=self.fallback_logger,
                        level=logging.WARNING
                    )
                    time.sleep(delay * attempt)
                else:
                    maybe_log_message(
                        'All %d attempts failed. Data not sent. '
                        'Last error: %s' % (max_retries, e),
                        logger=self.logger,
                        fallback_logger=self.fallback_logger,
                        level=logging.CRITICAL
                    )

                    raise RuntimeError(
                        'POST failed after %d attempts' % max_retries
                    )

    def fetch_command_from_controller(
        self, suffix='command/fetch/', timeout=5, api_key=None, **kwargs
    ):
        """
        Send GET request to controller to fetch the first pending
        command for a given server.
        """
        if not self.controller_url or not self.hostname:
            maybe_log_message(
                (
                    "Couldn't fetch controller command: controller URL or "
                    'hostname not set'
                ),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )
            return

        base_api_url = urljoin(self.controller_url, self.api_prefix)
        fetch_api_url = urljoin(base_api_url, suffix)
        url = '%s?hostname=%s' % (fetch_api_url, self.hostname)

        headers = {'Accept': 'application/json'}
        if api_key:
            headers.update(
                {'Authorization': '%s %s' % (self.auth_token_type, api_key)}
            )
        if kwargs:
            headers.update(kwargs)

        request = urllib2.Request(url, headers=headers)

        try:
            response = urllib2.urlopen(request, timeout=timeout)

            data = response.read()
            response.close()

            status_code = response.getcode()

            maybe_log_message(
                (
                    'GET request to controller succeded with '
                    'status: %s' % status_code
                ),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.INFO,
            )

            if status_code == 204 or not data.strip():
                maybe_log_message(
                    'No pending commands for server %s' % self.hostname,
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO,
                )

                return

            data = json.loads(data)

            return data
        except (urllib2.HTTPError, urllib2.URLError, socket.timeout) as e:
            maybe_log_message(
                (
                    'Failed to fetch command - GET request failed '
                    'due to error: %s' % str(e)
                ),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True,
            )
        except Exception as e:
            maybe_log_message(
                'GET request failed due to unexpected error: %s' % str(e),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True,
            )

    def maybe_add_to_queue(self, data):
        """
        Add command to queue if it passes field validation and if
        whitelisted by the server.
        """
        try:
            command_history = CommandHistory.from_dict(data)
        except (TypeError, ValueError) as e:
            maybe_log_message(
                'Command validation failed due to error: %s' % str(e),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )

            return

        if command_history.command in self.whitelist_commands:
            self.queue.put(command_history)

    def send_metrics_to_controller(
        self,
        suffix='agent/metrics/',
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
    ):
        """
        Sends a POST request with JSON data to the controller URL,
        including authentication, and built-in retry logic.
        """
        if not self.controller_url:
            maybe_log_message(
                "Couldn't send status update: controller URL is not set",
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )
            return
        base_api_url = urljoin(self.controller_url, self.api_prefix)
        metrics_api_url = urljoin(base_api_url, suffix)
        url = '%s?hostname=%s' % (metrics_api_url, self.hostname)

        payload = generate_report(self.logger, self.fallback_logger)
        try:
            result = self.post_data(
                url,
                payload,
                api_key,
                max_retries,
                delay,
                timeout
            )

            if result:
                maybe_log_message(
                    'POST request to controller succeeded.',
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO,
                )
            else:
                maybe_log_message(
                    'POST request to controller failed after retries.',
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    exc_info=True,
                )
        except Exception as e:
            maybe_log_message(
                'Unexpected error during status update: %s' % str(e),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True,
            )
