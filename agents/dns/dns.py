import pkg_resources

from ..agent import ServerAgent


class DNSAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_dir = pkg_resources.resource_filename(__name__, 'logs')
    server_name = 'dns'

    def __init__(self, dns_processes=None):
        super(DNSAgent, self).__init__()

        self.port = 53
        self.processes = dns_processes or ['named', 'bind9']
