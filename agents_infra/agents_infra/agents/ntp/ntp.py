from ..base import ServerAgent


class NTPAgent(ServerAgent):
    """
    Agent subclass for monitoring and managing an NTP daemon.
    """

    def __init__(
        self,
        server_name='ntp',
        protocol='udp',
        command_queue_size=0,
        config=None,
    ):
        super(NTPAgent, self).__init__(
            server_name=server_name,
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

    def is_service_healthy(
        self, timeout=2, payload=b'\x1b' + 47 * b'\0', packet_size=48
    ):
        """
        Check both the NTP process health and UDP port responsiveness.
        Returns True only if both are OK.
        """
        base_ok = super(NTPAgent, self).is_service_healthy()
        port_ok = self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
        return base_ok and port_ok
