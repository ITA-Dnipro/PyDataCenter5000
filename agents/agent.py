import abc
import pkg_resources
import logging.config
import platform
import socket
import json
import datetime
import logging

log_config_path = pkg_resources.resource_filename(
    "agents.logconfig", "logconfig.ini"
)


def get_hostname():
    try:
        return socket.gethostname()
    except socket.error:
        return "UNKNOWN"


def get_ip(hostname):
    try:
        return socket.gethostbyname(hostname)
    except (socket.gaierror, socket.error):
        return "UNKNOWN"


def get_linux_uptime():
    with open("/proc/uptime", "r") as f:
        return float(f.readline().split()[0])


def get_uptime(os_type):
    if "Linux" in os_type:
        return get_linux_uptime()

    return "UNKNOWN"


def get_timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


class ServerAgent(object):
    """
    Base class for all agents. Handles operations common for all
    servers, such as getting server metadata and writing it to logfile.
    """
    __metaclass__ = abc.ABCMeta

    server = None
    port = -1

    def __init__(self):
        self.os_type = platform.system() or "UNKNOWN"

        self.hostname = get_hostname()
        self.ip = get_ip(self.hostname)

        self.uptime = get_uptime(self.os_type)
        self.timestamp = get_timestamp()

        # Setup logging
        logging.config.fileConfig(
            log_config_path,
            defaults={"agent_name": self.server},
        )

        self.logger = logging.getLogger(self.server)

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
                "Port not set: server agent must assign a valid port number"
            )

        # Set a TCP/IP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.settimeout(2)
            s.connect((
                self.ip if self.ip != "UNKNOWN" else "localhost",
                self.port,
            ))
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
            "os": self.os_type,
            "hostname": self.hostname,
            "ip": self.ip,
            "uptime": self.uptime,
            "timestamp": self.timestamp,
            "healthy": self.service_healthy(),
        }

    def to_json(self):
        """Dump host metadata to json file."""
        try:
            msg = json.dumps(self.to_dict())
            self.logger.info(msg)
        except (IOError, OSError) as e:
            error_message = "Error logging to file: %s" % str(e)

            try:
                self.logger.error(error_message)
            except:
                logging.getLogger(
                    self.server + "_fallback"
                ).error(error_message)


    def to_txt(self):
        """Dump host metadata to txt file as key-value pairs."""
        data = self.to_dict()

        try:
            for k, v in data.items():
                msg = u"%s: %s" % (k, v)
                self.logger.info(msg.encode("utf-8"))
        except (IOError, OSError) as e:
            error_message = "Error logging to file: %s" % str(e)

            try:
                self.logger.error(error_message)
            except:
                logging.getLogger(
                    self.server + "_fallback"
                ).error(error_message)
