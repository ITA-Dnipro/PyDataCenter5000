import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):
    """
    SMTPAgent handles SMTP server configuration and logging setup.
    """
    def __init__(
        self,
        server_name='smtp',
        port=25,
        processes=None,
        interface=None,
        controller_url=None,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['postfix', 'exim', 'sendmail', 'master'],
            interface=interface,
            controller_url=controller_url,
        )
