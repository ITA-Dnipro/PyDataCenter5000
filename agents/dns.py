import logging

from .agent import ServerAgent


class DNSAgent(ServerAgent):
    server_name = 'dns'

    def __init__(self, dns_processes=None):
        super(DNSAgent, self).__init__()

        self.port = 53
        self.processes = dns_processes or ['named', 'bind9']
