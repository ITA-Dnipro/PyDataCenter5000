import logging
import socket

from ...utils.helpers import restart_service
from ..base import ServerAgent


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
        critical_processes=None,
        interface=None,
        protocol='tcp',
        whitelist_commands=None,
        command_queue_size=0,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or self.DEFAULT_PROCESSES,
            critical_processes=critical_processes,
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
            command_queue_size=command_queue_size,
        )

    def check_banner(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)

        banner = ''
        try:
            sock.connect((self.ip, self.port))
            banner = sock.recv(1024)
        except (socket.error, socket.timeout) as e:
            self.log_with_controller(
                'Banner check failed due to error: %s' % str(e),
                level=logging.ERROR
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

    def maybe_restart_service(self):
        inactive_services = []

        if not self.is_ssh_service_active():
            inactive_services.append('ssh')

        if inactive_services:
            for service in inactive_services:
                restart_service(service, logger=self.logger)

            self.log_with_controller(
                'Finished attempts to restart services',
                level=logging.INFO,
            )
            return False

        self.log_with_controller(
            'All services are healthy and running',
            level=logging.INFO,
        )
        return True
