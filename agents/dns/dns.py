from ..agent import ServerAgent


class DNSAgent(ServerAgent):

    def __init__(
        self,
        server_name='dns',
        port=53,
        processes=None,
        interface=None,
        protocol='udp',
        controller_url=None,
    ):
        super(DNSAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['named', 'bind9'],
            interface=interface,
            protocol=protocol,
            controller_url=controller_url,
        )

    def service_healthy(self, timeout=2, payload=None, packet_size=0):
        # TODO: extends check - send a DNS query and get a valid DNS response.
        return (
            self.is_process_running()
            and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
        )
