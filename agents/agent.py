import platform
import socket
import json
import datetime


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

    def __init__(self, logfile):
        self.logfile = logfile

        self.os_type = platform.system() or "UNKNOWN"

        self.hostname = get_hostname()
        self.ip = get_ip(self.hostname)

        self.uptime = get_uptime(self.os_type)
        self.timestamp = get_timestamp()

    def to_dict(self):
        return {
            "os": self.os_type,
            "hostname": self.hostname,
            "ip": self.ip,
            "uptime": self.uptime,
            "timestamp": self.timestamp,
        }

    def to_json(self):
        with open(self.logfile, "w") as f:
            json.dump(self.to_dict(), f)

    def to_txt(self):
        data = self.to_dict()

        with open(self.logfile, "w") as f:
            for k, v in data.items():
                f.write("%s: %s\n" % (k, v))
