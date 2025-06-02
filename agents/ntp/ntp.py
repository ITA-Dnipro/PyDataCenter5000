from ..agent import ServerAgent


class NTPAgent(ServerAgent):

    def __init__(
        self,
        server_name='ntp',
        port=123,
        processes=None,
        interface=None,
        protocol='udp',
        controller_url=None,
    ):
        super(NTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['ntpd', 'chronyd', 'systemd-timesyncd'],
            interface=interface,
            protocol=protocol,
            controller_url=controller_url,
        )

    def service_healthy(
        self, timeout=2, payload=b'\x1b' + 47 * b'\0', packet_size=48
    ):
        return (
            self.is_process_running()
            and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
        )
