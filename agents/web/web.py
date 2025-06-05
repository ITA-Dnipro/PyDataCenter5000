import os

from ..agent import ServerAgent


class WebAgent(ServerAgent):

    def __init__(
        self,
        server_name='web',
        port=8000,
        processes=None,
        interface=None,
        protocol='tcp',
        controller_url=None,
        log_path=None,
    ):
        if port is None and 'PORT' not in os.environ:
            raise ValueError('WEB port environment variable is not set.')

        port = port or int(os.environ['PORT'])

        super(WebAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['uvicorn'],
            interface=interface,
            protocol=protocol,
            controller_url=controller_url,
            log_path=log_path,
        )

    def service_healthy(
            self, timeout=2, payload=None, packet_size=0
    ):
        # TODO: extend health check.
        status = super(WebAgent, self).service_healthy()
        return status and self.is_port_open(
            timeout=timeout, payload=payload, packet_size=packet_size
        )
