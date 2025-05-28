import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):

    def __init__(
        self,
        server_name='smtp',
        port=25,
        processes=None,
        controller_url=None,
        config_file=None,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['postfix', 'exim', 'sendmail', 'master'],
            controller_url=controller_url,
            config_file=(
                config_file
                or pkg_resources.resource_filename(__name__, 'config.ini')
            ),
        )
