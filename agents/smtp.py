import subprocess
import logging
from .agent import ServerAgent


class SMTPAgent(ServerAgent):
    server_name = "smtp"
    port = 25

    def __init__(self, smtp_processes=None):
        super(SMTPAgent, self).__init__()

        self.processes = smtp_processes or ["postfix", "exim", "sendmail", "master"]

    def service_healthy(self):
        try:
            output = subprocess.Popen(
                ["ps", "aux"], stdout=subprocess.PIPE
            ).communicate()[0]

            if hasattr(output, "decode"):
                output = output.decode("utf-8")
            output = output.lower()

            return (
                self.port_open()
                and any(proc in output for proc in self.processes)
            )
        except OSError as e:
            error_message = "SMTP check failed: %s" % str(e)

            try:
                self.logger.error(error_message)
            except:
                logging.getLogger(
                    self.server_name + "_fallback"
                ).error(error_message)

            return False
