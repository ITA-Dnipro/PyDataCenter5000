import socket
import json
import time


class ServerAgent(object):

    def __init__(self, logfile):
        self.logfile = logfile

        self.hostname = self.get_hostname()
        self.ip = self.get_ip()

    def get_hostname(self):
        return socket.gethostname()

    def get_ip(self):
        return socket.gethostbyname(self.hostname)

    def to_dict(self):
        return {
            "hostname": self.hostname,
            "ip": self.ip,
        }

    def to_json(self):
        with open(self.logfile, "w") as f:
            json.dump(self.to_dict(), f)

    def to_txt(self):
        data = self.to_dict()

        with open(self.logfile, "w") as f:
            for k, v in data.items():
                f.write("%s: %s\n" % (k, v))