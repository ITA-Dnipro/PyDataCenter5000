import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):
    server_name = 'smtp'
    port = 25
    processes = ['postfix', 'exim', 'sendmail', 'master']
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_path = pkg_resources.resource_filename(__name__, 'logs/agent.log')

    def __init__(
        self,
        server_name=None,
        port=None,
        processes=None,
        controller_url=None,
        config_file=None,
        log_path=None,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes,
            controller_url=controller_url,
            config_file=config_file,
            log_path=log_path,
        )
