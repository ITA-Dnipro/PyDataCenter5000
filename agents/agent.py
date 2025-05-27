import abc
import datetime
import json
import logging
import logging.config
import platform
import socket
import subprocess

import ConfigParser
import pkg_resources
import psutil
import urllib2

from .utils.helpers import get_config_option
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
    addresses = psutil.net_if_addrs()[interface]

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

    config_file = None
    log_path = None
    server_name = None
    port = -1
    controller_url = None

    def __init__(self, log_path=None):
        # Setup logging
        if log_path:
            self.log_path = log_path

        logging.config.fileConfig(
            log_config_path,
            defaults={
                'agent_name': self.server_name, 'log_path': self.log_path
            },
        )

        self.logger = logging.getLogger(self.server_name)
        self.fallback_logger = logging.getLogger(
            '_'.join([self.server_name, 'fallback'])
        )

        self.processes = []

        self._parse_config_file()

        self._set_server_metadata()

    def _parse_config_file(self):
        """Parse server's config file using ConfigParser."""
        config = ConfigParser.ConfigParser()

        if self.config_file:
            config.read(self.config_file)

            if config.sections():
                self.interface = get_config_option(
                    config,
                    'server',
                    'interface',
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                )

                self.controller_url = get_config_option(
                    config,
                    'controller',
                    'url',
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                )

    def _set_server_metadata(self):
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
            output = subprocess.Popen(
                ['ps', 'aux'], stdout=subprocess.PIPE
            ).communicate()[0]

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
            status = json.dumps(self.status_to_dict())

            if log:
                try:
                    self.logger.info(status)
                except (IOError, OSError) as e:
                    maybe_log_message(
                        'Error logging to file: %s' % str(e),
                        self.logger,
                        fallback_logger=self.fallback_logger,
                    )
                finally:
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
        data = self.to_dict()

        try:
            for k, v in data.items():
                self.logger.info(u'%s: %s' % (k, v))
        except (IOError, OSError) as e:
            maybe_log_message(
                'Error logging to file: %s' % str(e),
                self.logger,
                fallback_logger=self.fallback_logger,
            )

    def status_to_controller(self, timeout=5, api_key=None):
        """
        Send system's metadata to controller.

        Parameters:
            timeout (int): POST request timeout in seconds. Default is 5.
            api_key (str): Authentication API key. Default is None.
        """
        if not self.controller_url:
            maybe_log_message(
                "Couldn't send status update: controller URL is not set",
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )

            return

        payload = self.status_to_json(log=False)

        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers.update({'X-API-Key': api_key})

        request = urllib2.Request(
            self.controller_url, payload, headers=headers
        )

        status_code = None

        try:
            response = urllib2.urlopen(request, timeout=timeout)
            status_code = response.getcode()
        except (urllib2.URLError, urllib2.HTTPError) as e:
            status_code = getattr(e, 'code', None)

            maybe_log_message(
                'POST request to controller failed due to error: %s' % str(e),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True,
            )
        finally:
            if status_code:
                maybe_log_message(
                    'POST request status: %s' % str(status_code),
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO,
                )
