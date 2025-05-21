import abc
import platform
import socket
import json
import datetime
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


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

    def __init__(self, logger):
        self.logger = logger

        self.os_type = platform.system() or "UNKNOWN"

        self.hostname = get_hostname()
        self.ip = get_ip(self.hostname)

        self.uptime = get_uptime(self.os_type)
        self.timestamp = get_timestamp()

        # Subclass must set port
        self.port = -1

    @classmethod
    def with_rotating_logger(
        cls,
        logfile,
        name=None,
        formatter=None,
        when="midnight",
        interval=1,
        count=7,
    ):
        """
        Factory method to instantiate the agent with a timed rotating
        logger.

        Parameters:
            logfile (str): Name of the base log file.
            name (str): Name of the logger. If none is given, the name
                will be the same as that of the agent class.
            formatter (Formatter): Logging formatter. Default is None.
            when (str): When to rotate the log file. Default is
                'midnight' - a new timestamped log file will is created
                at midnight.
            interval (int): Periodicity which determines how often to
                rotate log files. Default is 1.
            count (int): Number of old log files to keep. Default is 7.
        """
        logger = logging.getLogger(name or cls.__name__)
        logger.setLevel(logging.INFO)

        handler = TimedRotatingFileHandler(
            logfile, when=when, interval=interval, backupCount=count
        )

        formatter = formatter or logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return cls(logger)

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
                self.hostname if self.hostname != "UNKNOWN" else "localhost",
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
            logger.error("Error writing to %s: %s" % (self.logfile, e))

    def to_txt(self):
        """Dump host metadata to txt file as key-value pairs."""
        data = self.to_dict()

        try:
            for k, v in data.items():
                msg = u"%s: %s" % (k, v)
                self.logger.info(msg.encode("utf-8"))
        except (IOError, OSError) as e:
            logger.error("Error writing to %s: %s" % (self.logfile, e))
