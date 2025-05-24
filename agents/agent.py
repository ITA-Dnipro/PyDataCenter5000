import abc
import datetime
import json
import logging
import logging.config
import platform
import socket

import pkg_resources
import psutil

from .utils.logtools import maybe_log_error

log_config_path = pkg_resources.resource_filename(
    'agents.utils.logtools', 'logconfig.ini'
)


def get_ip_from_interface(netiface):
    addresses = psutil.net_if_addrs()[netiface]

    for address in addresses:
        if address.address.startswith('127.'):
            continue

        if address.family == socket.AF_INET:
            return address.address


def get_linux_uptime():
    with open('/proc/uptime', 'r') as f:
        return float(f.readline().split()[0])


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """
    __metaclass__ = abc.ABCMeta

    server_name = None
    port = -1

    def __init__(self, netiface=None):
        # Setup logging
        logging.config.fileConfig(
            log_config_path,
            defaults={'agent_name': self.server_name},
        )

        self.logger = logging.getLogger(self.server_name)
        self.fallback_logger = logging.getLogger(
            self.server_name + '_fallback'
        )

        self.set_server_metadata(netiface)

    def set_server_metadata(self, netiface=None):
        system = platform.system()
        if not system:
            maybe_log_error(
                'Could not deduce OS type', self.logger, self.fallback_logger
            )

        self.os_type = system.lower() or 'unknown'

        try:
            self.hostname = socket.gethostname()
        except socket.error as e:
            self.hostname = 'unknown'

            maybe_log_error(
                'Could not get hostname: %s' % str(e),
                self.logger,
                self.fallback_logger,
            )

        self.ip = None

        if netiface:
            try:
                self.ip = get_ip_from_interface(netiface)
            except (KeyError, AttributeError) as e:
                maybe_log_error(
                    (
                        'Could not deduce IP address from interface '
                        '%s: %s' % netiface, str(e)
                    ),
                    self.logger,
                    self.fallback_logger,
                )

        if not self.ip and self.hostname != 'UNKNOWN':
            try:
                self.ip = socket.gethostbyname(self.hostname)
            except (socket.gaierror, socket.error) as e:
                maybe_log_error(
                    'Could not deduce IP address from hostname: %s' % str(e),
                    self.logger,
                    self.fallback_logger,
                )

        self.uptime = -1

        if 'linux' in self.os_type:
            self.uptime = get_linux_uptime()

        if self.uptime < 0:
            maybe_log_error(
                "Could not get system's uptime",
                self.logger,
                self.fallback_logger,
            )

        self.timestamp = datetime.datetime.utcnow().strftime(
            '%Y-%m-%d %H:%M:%S'
        )

    def port_open(self):
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

    @abc.abstractmethod
    def service_healthy(self):
        """
        Check if the specific service (SMTP, DNS, etc.) is running and
        healthy.
        """
        pass

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
            maybe_log_error(
                'Error logging to file: %s' % str(e),
                self.logger,
                self.fallback_logger,
            )

    def to_txt(self):
        """Dump host metadata to txt file as key-value pairs."""
        data = self.to_dict()

        try:
            for k, v in data.items():
                self.logger.info(u'%s: %s' % (k, v))
        except (IOError, OSError) as e:
            maybe_log_error(
                'Error logging to file: %s' % str(e),
                self.logger,
                self.fallback_logger,
            )
