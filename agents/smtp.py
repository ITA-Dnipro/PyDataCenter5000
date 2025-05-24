import logging
import subprocess

from .agent import ServerAgent
from .utils.logtools import maybe_log_error


class SMTPAgent(ServerAgent):
    server_name = 'smtp'
    port = 25

    def __init__(self, netiface=None, smtp_processes=None):
        super(SMTPAgent, self).__init__(netiface)

        self.processes = (
            smtp_processes or ['postfix', 'exim', 'sendmail', 'master']
        )

    def service_healthy(self):
        try:
            output = subprocess.Popen(
                ['ps', 'aux'], stdout=subprocess.PIPE
            ).communicate()[0]

            if hasattr(output, 'decode'):
                output = output.decode('utf-8')
            output = output.lower()

            return (
                self.port_open()
                and any(proc in output for proc in self.processes)
            )
        except OSError as e:
            maybe_log_error(
                'SMTP check failed: %s' % str(e),
                self.logger,
                self.fallback_logger,
            )

            return False
