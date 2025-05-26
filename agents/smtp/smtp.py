import subprocess

import pkg_resources

from ..agent import ServerAgent
from ..utils.logtools import maybe_log_message


class SMTPAgent(ServerAgent):
    config_file = pkg_resources.resource_filename(__name__, 'config.ini')
    log_dir = pkg_resources.resource_filename(__name__, 'logs')
    server_name = 'smtp'
    port = 25

    def __init__(self, smtp_processes=None):
        super(SMTPAgent, self).__init__()

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
            maybe_log_message(
                'SMTP check failed: %s' % str(e),
                self.logger,
                fallback_logger=self.fallback_logger,
            )

            return False
