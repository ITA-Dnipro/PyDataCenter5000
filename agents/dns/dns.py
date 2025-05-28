import pkg_resources

from ..agent import ServerAgent


class DNSAgent(ServerAgent):

    def __init__(
        self,
        server_name='dns',
        port=53,
        processes=None,
        interface=None,
        controller_url=None,
        config_file=None,
    ):
        super(DNSAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['named', 'bind9'],
            interface=interface,
            controller_url=controller_url,
            config_file=(
                config_file
                or pkg_resources.resource_filename(__name__, 'config.ini')
            ),
        )
