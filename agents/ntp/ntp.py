import socket

import pkg_resources

from ..agent import ServerAgent


class NTPAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_dir = pkg_resources.resource_filename(__name__, 'logs')
    server_name = 'ntp'

    protocol = 'udp'
    udp_probe_payload = b'\x1b' + 47 * b'\0'
    udp_probe_response_len = 48

    def __init__(self, ntp_processes=None):
        super(NTPAgent, self).__init__()
        self.port = 123
        self.processes = ntp_processes or [
            'ntpd', 'chronyd', 'systemd-timesyncd'
        ]
