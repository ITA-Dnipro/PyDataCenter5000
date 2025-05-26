import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_dir = pkg_resources.resource_filename(__name__, 'logs')
    server_name = 'smtp'

    def __init__(self, smtp_processes=None):
        super(SMTPAgent, self).__init__()

        self.port = 25
        self.processes = smtp_processes or [
            'postfix', 'exim', 'sendmail', 'master'
        ]
