import subprocess
from .agent import ServerAgent


class SMTPAgent(ServerAgent):
    server = "smtp"
    port = 25

    def __init__(self, smtp_processes=None):
        super(SMTPAgent, self).__init__()

        self.processes = smtp_processes or ["postfix", "exim", "sendmail"]

    def service_healthy(self):
        try:
            output = subprocess.Popen(
                ["ps", "aux"], stdout=subprocess.PIPE
            ).communicate()[0]
            output = output.lower()

            return (
                self.port_open()
                and any(proc in output for proc in self.processes)
            )
        except Exception:
            return False
