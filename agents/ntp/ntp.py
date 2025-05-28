import socket

import pkg_resources

from ..agent import ServerAgent


class NTPAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_dir = pkg_resources.resource_filename(__name__, 'logs')
    server_name = 'ntp'

    def __init__(self, ntp_processes=None):
        super(NTPAgent, self).__init__()
        self.port = 123
        self.processes = ntp_processes or [
            'ntpd', 'chronyd', 'systemd-timesyncd'
        ]

    def _is_port_open(self):
        """Check UDP 123 instead of TCP."""
        if self.port == -1:
            raise ValueError('Port not set')
        if not self.ip:
            return False

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(2)
            s.sendto(b'', (self.ip, self.port))
            return True
        except socket.error:
            return False
        finally:
            s.close()
