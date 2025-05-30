from ..agent import ServerAgent


class NTPAgent(ServerAgent):

    protocol = 'udp'
    udp_probe_payload = b'\x1b' + 47 * b'\0'
    udp_probe_response_len = 48

    def __init__(
        self,
        server_name='ntp',
        port=123,
        processes=None,
        interface=None,
        controller_url=None,
    ):
        super(NTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['ntpd', 'chronyd', 'systemd-timesyncd'],
            interface=interface,
            controller_url=controller_url,
        )
