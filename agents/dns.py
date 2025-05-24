import logging
import subprocess

from .agent import ServerAgent


class DNSAgent(ServerAgent):
    server_name = 'dns'
    port = 53

    def __init__(self, smtp_processes=None):
        super(DNSAgent, self).__init__()

        self.processes = smtp_processes or ['named', 'bind9']

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
            error_message = 'DNS check failed: %s' % str(e)

            try:
                self.logger.error(error_message)
            except Exception:
                logging.getLogger(
                    self.server_name + '_fallback'
                ).error(error_message)

            return False
