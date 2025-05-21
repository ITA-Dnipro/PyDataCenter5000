import subprocess
from .agent import ServerAgent


class SMTPAgent(ServerAgent):

    def __init__(self, logfile):
        super(SMTPAgent, self).__init__(logfile)

        self.port = 25

    def service_healthy(self):
        try:
            output = subprocess.Popen(
                ["ps", "aux"], stdout=subprocess.PIPE
            ).communicate()[0]
            output = output.lower()

            return (
                self.port_open()
                and any(
                    process in output
                    for process in ["postfix", "exim", "sendmail"]
                )
            )
        except Exception:
            return False
