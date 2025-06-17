import os

from ..agent import ServerAgent


class WebAgent(ServerAgent):

    def __init__(
        self,
        server_name='web',
        port=None,
        processes=None,
        interface=None,
        protocol='tcp',
        whitelist_commands=None,
        log_path=None,
        command_queue_size=0,
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
            whitelist_commands=whitelist_commands,
            log_path=log_path,
            command_queue_size=command_queue_size,
        )

    def service_healthy(
        self, timeout=2, payload=None, packet_size=0
    ):
        # TODO: extend health check.
        status = super(WebAgent, self).service_healthy()
        return status and self.is_port_open(
            timeout=timeout, payload=payload, packet_size=packet_size
        )
