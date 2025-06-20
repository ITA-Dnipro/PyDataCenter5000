import os

from ..agent import ServerAgent


class WebAgent(ServerAgent):

    def __init__(
        self,
        server_name='web',
        port=8000,
        critical_processes=None,
        interface=None,
        protocol='tcp',
        whitelist_commands=None,
    ):
        if port is None and 'PORT' not in os.environ:
            raise ValueError('WEB port environment variable is not set.')

        port = port or int(os.environ['PORT'])

        super(WebAgent, self).__init__(
            server_name=server_name,
            port=port,
            critical_processes=critical_processes,
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
        )

    def is_service_healthy(
            self, timeout=2, payload=None, packet_size=0
    ):
        # TODO: extend health check.
        status = super(WebAgent, self).is_service_healthy()
        return status and self.is_port_open(
            timeout=timeout, payload=payload, packet_size=packet_size
        )
