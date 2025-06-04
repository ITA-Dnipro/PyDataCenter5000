import os

from ..agent import ServerAgent


class WebAgent(ServerAgent):

    def __init__(
        self,
        server_name='web',
        port=8000,
        processes=None,
        interface=None,
        whitelist_commands=None,
    ):
        if port is None and 'PORT' not in os.environ:
            raise ValueError('WEB port environment variable is not set.')

        port = port or int(os.environ['PORT'])

        super(WebAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['uvicorn'],
            interface=interface,
            whitelist_commands=whitelist_commands,
        )

    def service_healthy(
            self, timeout=2, payload=None, packet_size=0
    ):
        status = super(WebAgent, self).service_healthy()
        return status and self.is_port_open(
            timeout=timeout, payload=payload, packet_size=packet_size
        )
