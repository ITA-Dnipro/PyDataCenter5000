import abc
import socket

from ...utils.logtools import maybe_log_message
from ..base import ServerAgent


class SMTPAgent(ServerAgent):

    __metaclass__ = abc.ABCMeta

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
        protocol='tcp',
        command_queue_size=0,
        config=None,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

    def check_banner(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)

        banner = ''
        try:
            sock.connect((self.ip, self.config.get('port')))
            banner = sock.recv(1024)
        except (socket.error, socket.timeout) as e:
            maybe_log_message(
                'Banner check failed due to error: %s' % str(e),
                logger=self.logger,
            )
        finally:
            sock.close()

        return banner.strip() if banner else ''

    def is_service_healthy(self):
        status = super(SMTPAgent, self).is_service_healthy()
        return status and bool(self.check_banner())

    def status_to_dict(self):
        status = super(SMTPAgent, self).status_to_dict()

        banner = self.check_banner()
        status['banner'] = banner if banner else None

        return status


class SMTPAgentPostfix(SMTPAgent):
    """
    Specialized SMTPAgent subclass for managing the 'postfix' service.

    Inherits SMTPAgent functionality, configured for Postfix SMTP server.
    """

    def __init__(
        self,
        server_name='smtp_postfix',
        protocol='tcp',
        command_queue_size=0,
        config=None
    ):
        super(SMTPAgentPostfix, self).__init__(
            server_name=server_name,
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )
