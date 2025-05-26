import logging

from .agent import ServerAgent


class SMTPAgent(ServerAgent):
    server_name = 'smtp'

    def __init__(self, smtp_processes=None):
        super(SMTPAgent, self).__init__()

        self.port = 25
        self.processes = smtp_processes or [
            'postfix', 'exim', 'sendmail', 'master'
        ]
