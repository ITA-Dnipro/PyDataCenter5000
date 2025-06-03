import abc
import datetime
import json
import logging
import logging.config
import platform
import socket
import subprocess
import time
from collections import Sequence

import ConfigParser
import pkg_resources
import psutil
import urllib2

from .utils.helpers import get_config_option, parse_csv_list
from .utils.logtools import maybe_log_message

log_config_path = pkg_resources.resource_filename(
    'agents.utils.logtools', 'logconfig.ini'
)


def get_ip_from_interface(interface):
    """
    Attempt getting server's primary IP address associated with a given
    interface name.

    Parameters:
        interface (str): Interface name.

    Returns:
        str: On success, IP address is returned.
    """
    net_if_dict = psutil.net_if_addrs()
    if interface not in net_if_dict:
        return

    addresses = net_if_dict[interface]

    for address in addresses:
        if address.address.startswith('127.'):
            continue

        if address.family == socket.AF_INET:
            return address.address


def get_linux_uptime():
    """Get uptime on Linux OS."""
    with open('/proc/uptime', 'r') as f:
        return float(f.readline().split()[0])


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

    def __init__(
        self,
        server_name=None,
        port=None,
        processes=None,
        interface=None,
        whitelist_commands=None,
    ):
        self.server_name = server_name
        self.port = port if port is not None else self.port
        self.processes = processes if processes is not None else self.processes
        self.interface = interface

        if self.whitelist_commands is None:
            self.whitelist_commands = []

        if whitelist_commands is not None:
            self.whitelist_commands.extend(whitelist_commands)

        # Init server metadata to prevent AttributeError and to indicate
        # to user that collect_server_metadata hasn't been called.
        self.os_type = self.hostname = self.ip = None
        self.uptime = self.timestamp = None

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

        agent.setup_logging(path=log_path)
        agent._parse_config_file(filename)

        return agent

    @property
    def port(self):
        return getattr(self, '_port', -1)

    @port.setter
    def port(self, value):
        if not isinstance(value, int):
            raise TypeError('Port number must be an integer')
        self._port = value

    @property
    def processes(self):
        return getattr(self, '_processes', [])

    @processes.setter
    def processes(self, value):
        if not isinstance(value, Sequence):
            raise TypeError(
                (
                    'Process names must be provided as a string or a sequence '
                    '(list, tuple etc.), not %s' % type(value)
                )
            )
        self._processes = value

    def setup_logging(self, path=None):
        # Have each child dump logs inside their own subpackage by default
        path = (
            path or pkg_resources.
            resource_filename(self.__class__.__module__, 'logs/agent.log')
        )

        logging.config.fileConfig(
            log_config_path,
            defaults={
                'agent_name': self.server_name,
                'log_path': path
            },
        )

        self.logger = logging.getLogger(self.server_name)
        self.fallback_logger = logging.getLogger(
            '_'.join([self.server_name, 'fallback'])
        )

    def _parse_config_file(self, filename=None):
        """Parse server's config file using ConfigParser."""
        filename = (
            filename or pkg_resources.
            resource_filename(self.__class__.__module__, 'config.ini')
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

            self.processes = get_config_option(
                config,
                'server',
                'processes',
                default=self.processes,
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                cast=parse_csv_list,
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
                [],
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                cast=parse_csv_list,
            )
            # Add commands to the list of globally allowed commands.
            if whitelist_commands:
                self.whitelist_commands.extend(whitelist_commands)

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

        self.timestamp = datetime.datetime.utcnow(
        ).strftime('%Y-%m-%d %H:%M:%S')

    def _is_port_open(self):
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

        # Set a TCP/IP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.settimeout(2)
            s.connect((self.ip, self.port))
        except socket.error:
            return False
        finally:
            s.close()

        return True

    def _is_process_running(self):
        try:
            output = subprocess.Popen(['ps', 'aux'],
                                      stdout=subprocess.PIPE).communicate()[0]

            if hasattr(output, 'decode'):
                output = output.decode('utf-8')
            output = output.lower()

            return any(proc in output for proc in self.processes)
        except OSError as e:
            maybe_log_message(
                'Process check failed: %s' % e,
                self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True,
            )

            return False

    def service_healthy(self):
        """
        Check if the specific service (SMTP, DNS, etc.) is running and
        healthy.
        """
        return self._is_port_open() and self._is_process_running()

    def status_to_dict(self):
        return {
            'os': self.os_type,
            'hostname': self.hostname,
            'ip': self.ip,
            'server_name': self.server_name,
            'uptime': self.uptime,
            'timestamp': self.timestamp,
            'healthy': self.service_healthy(),
        }

    def status_to_json(self, log=False):
        """
        Dump host metadata to json file.

        Parameters:
            log (bool): Whether to log JSON status string to the logfile.
                Default is False.

        Returns:
            str: JSON status string.
        """
        try:
            status = json.dumps(self.status_to_dict(), default=str)

            if log:
                try:
                    self.logger.info(status)
                except (IOError, OSError) as e:
                    maybe_log_message(
                        'Error logging to file: %s' % str(e),
                        self.logger,
                        fallback_logger=self.fallback_logger,
                    )

            return status
        except TypeError as e:
            maybe_log_message(
                (
                    'JSON serialization of status failed '
                    'due to error: %s' % str(e)
                ),
                self.logger,
                fallback_logger=self.fallback_logger,
            )

    def status_to_txt(self):
        """Dump host metadata to txt file as key-value pairs."""
        data = self.status_to_dict()

        try:
            for k, v in data.items():
                self.logger.info(u'%s: %s' % (k, v))
        except (IOError, OSError) as e:
            maybe_log_message(
                'Error logging to file: %s' % str(e),
                self.logger,
                fallback_logger=self.fallback_logger,
            )

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
            except urllib2.URLError as e:
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

    def status_to_controller(
        self, api_key=None, max_retries=3, delay=5, timeout=5
    ):
        """
        Sends a POST request with JSON data to the specified URL, including
        optional authentication, and with built-in retry logic.

        Parameters:
            url (str): Target URL for the POST request.
            data (dict): Data to send as JSON payload.
            auth_token_type (str): Token type prefix for the Authorization
                header (e.g., 'Bearer').
            api_key (str): API key to be used for the Authorization header. If
                None, no auth header is added.
            max_retries (int): Maximum number of retry attempts on failure.
                Default is MAX_RETRIES.
            delay (int | float): Delay (in seconds) between
        """
        if not self.controller_url:
            maybe_log_message(
                "Couldn't send status update: controller URL is not set",
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )
            return

        payload_str = self.status_to_json(log=False)
        payload = json.loads(payload_str)

        try:
            result = self.post_data(
                self.controller_url,
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
        except (urllib2.HTTPError, urllib2.URLError, socket.timeout) as e:
            maybe_log_message(
                'POST request to controller failed due to error: %s' % str(e),
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

    def fetch_command_from_controller(
        self, api_key=None, suffix='command/', timeout=5
    ):
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

        url = (
            self.controller_url
            + self.api_prefix
            + suffix
            + '?hostname=%s' % self.hostname
        )

        headers = {'Accept': 'application/json'}
        if api_key:
            headers.update(
                {'Authorization': '%s %s' % (self.auth_token_type, api_key)}
            )

        request = urllib2.Request(url, headers=headers)

        try:
            response = urllib2.urlopen(request, timeout=timeout)

            data = response.read()
            response.close()

            return json.loads(data)
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
        except ValueError:
            maybe_log_message(
                'Data received from controller is not a valid JSON string',
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
