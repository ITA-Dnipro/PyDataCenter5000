from __future__ import print_function
from utils.logtools import maybe_log_message
import socket
import pkg_resources

from agent.agent import ServerAgent

class SMTPAgent(ServerAgent):
    DEFAULT_PROCESSES = ['postfix', 'exim', 'sendmail', 'master']
    """
    SMTPAgent performs health checks for an SMTP server:
    - verifies if the port is open
    - checks whether specified processes are running
    - attempts to receive the SMTP banner
    Compatible with Python 2.6.
    """
    def __init__(self,
                 server_name='smtp',
                 port=25,
                 processes=None,
                 interface=None,
                 controller_url=None):
        ServerAgent.__init__(
            self,
            server_name=server_name,
            port=port,
            processes=processes or self.DEFAULT_PROCESSES,
            interface=interface,
            controller_url=controller_url,
        )
        self.setup_logging()

    def collect_server_metadata(self):
        return super(SMTPAgent, self).collect_server_metadata()

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

    def check_port(self):
        return self._is_port_open()
        

    def check_processes(self):
        return self._is_process_running()
        
    def service_healthy(self):
        port_ok = self.check_port()
        processes_ok = self.check_processes()
        banner = self.check_banner()
        return port_ok and processes_ok and bool(banner)
    
    def status_to_dict(self):
        data = super(SMTPAgent, self).status_to_dict()
        banner = self.check_banner()
        data['banner_check'] = {
            'status': 'ok' if banner else 'no banner',
            'banner': banner if banner else None
        }
        return data