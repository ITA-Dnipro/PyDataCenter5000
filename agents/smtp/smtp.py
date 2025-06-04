import socket

from ..agent import ServerAgent
from ..utils.logtools import maybe_log_message


class SMTPAgent(ServerAgent):
    DEFAULT_PROCESSES = ['postfix', 'exim', 'sendmail', 'master']
    """
    SMTPAgent performs health checks for an SMTP server:
    - verifies if the port is open
    - checks whether specified processes are running
    - attempts to receive the SMTP banner
    Compatible with Python 2.6.
    """
    def __init__(
        self,
        server_name='smtp',
        port=25,
        processes=None,
        interface=None,
        whitelist_commands=None,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or self.DEFAULT_PROCESSES,
            interface=interface,
            whitelist_commands=whitelist_commands,
        )

    def check_banner(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)

        banner = ''
        try:
            sock.connect((self.ip, self.port))
            banner = sock.recv(1024)
        except (socket.error, socket.timeout) as e:
            maybe_log_message(
                'Banner check failed due to error: %s' % str(e),
                logger=self.logger,
                fallback_logger=self.fallback_logger,
            )
        finally:
            sock.close()

        return banner.strip() if banner else ''

    def service_healthy(self):
        status = super(SMTPAgent, self).service_healthy()
        return status and self.check_banner()

    def status_to_dict(self):
        status = super(SMTPAgent, self).status_to_dict()

        banner = self.check_banner()
        status['banner'] = banner if banner else None

        return status
