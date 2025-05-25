import logging

from .agent import ServerAgent


class DNSAgent(ServerAgent):
    server_name = 'dns'
    port = 53

    def __init__(self, dns_processes=None):
        super(DNSAgent, self).__init__()

        self.processes = dns_processes or ['named', 'bind9']
