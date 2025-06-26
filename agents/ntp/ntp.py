from ..agent import ServerAgent


class NTPAgent(ServerAgent):

    def __init__(
        self,
        server_name='ntp',
        protocol='udp',
        command_queue_size=0,
        config=None
    ):
        super(NTPAgent, self).__init__(
            server_name=server_name,
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

    def service_healthy(
        self, timeout=2, payload=b'\x1b' + 47 * b'\0', packet_size=48
    ):
        status = super(NTPAgent, self).is_service_healthy()
        return status and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
