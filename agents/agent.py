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

    # Protocol for port check: 'tcp' or 'udp'
    protocol = 'tcp'
    # Optional UDP probe settings for subclasses
    udp_probe_payload = b''
    udp_probe_response_len = 0

    config_file = None
    log_dir = None
    server_name = None
    processes = []
    port = -1

    def __init__(self):
        # Setup logging
        logging.config.fileConfig(
            log_config_path,
            defaults={'agent_name': self.server_name, 'log_dir': self.log_dir},
        )

        self.logger = logging.getLogger(self.server_name)
        self.fallback_logger = logging.getLogger(
            '_'.join([self.server_name, 'fallback'])
        )

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

        if self.protocol.lower() == 'udp':
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.settimeout(2)
                payload = self.udp_probe_payload or b''
                sock.sendto(payload, (self.ip, self.port))
                # if a response length is specified, wait for reply
                if self.udp_probe_response_len > 0:
                    data, _ = sock.recvfrom(self.udp_probe_response_len)
                    if data and len(data) >= self.udp_probe_response_len:
                        return True
                    self.logger.warning(
                        'Received unexpected UDP packet length %d', len(data)
                    )
                    return False
                return True
            except socket.timeout:
                self.logger.warning(
                    '%s UDP check to %s:%d timed out',
                    self.server_name, self.ip, self.port
                )
                return False
            except socket.error as e:
                self.logger.warning(
                    '%s UDP check failed for %s:%d - %s',
                    self.server_name, self.ip, self.port, e
                )
                return False
            finally:
                sock.close()

        # Default TCP behavior
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(2)
            sock.connect((self.ip, self.port))
            return True
        except socket.error as e:
            self.logger.warning(
                '%s TCP port check failed for %s:%d - %s',
                self.server_name, self.ip, self.port, e
            )
            return False
        finally:
            sock.close()

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

    def to_dict(self):
        return {
            'os': self.os_type,
            'hostname': self.hostname,
            'ip': self.ip,
            'server_name': self.server_name,
            'uptime': self.uptime,
            'timestamp': self.timestamp,
            'healthy': self.service_healthy(),
        }

    def to_json(self):
        """Dump host metadata to json file."""
        try:
            msg = json.dumps(self.to_dict())
            self.logger.info(msg)
        except (IOError, OSError) as e:
            maybe_log_message(
                'Error logging to file: %s' % str(e),
                self.logger,
                fallback_logger=self.fallback_logger,
            )

    def to_txt(self):
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
