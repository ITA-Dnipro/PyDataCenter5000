import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_path = pkg_resources.resource_filename(__name__, 'logs/agent.log')
    server_name = 'smtp'

    def __init__(self, log_path=None, smtp_processes=None):
        super(SMTPAgent, self).__init__(log_path=log_path)

        self.port = 25
        self.processes = smtp_processes or [
            'postfix', 'exim', 'sendmail', 'master'
        ]
