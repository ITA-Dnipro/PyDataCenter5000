import abc
import socket

from ...utils.configtools import Config
from ...utils.logtools import maybe_log_message
from ...utils.sysinfo import is_port_open
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
        protocol='tcp',
        command_queue_size=0,
        config=None,
    ):
        if config is None:
            config = Config(name='smtp', protocol=protocol)
        elif isinstance(config, dict):
            config.setdefault('name', 'smtp')
            config.setdefault('protocol', protocol)
            config = Config.from_dict(config)
        elif isinstance(config, Config):
            if not config.name:
                config.name = 'smtp'
            if not getattr(config, 'protocol', None):
                config.protocol = protocol

        super(SMTPAgent, self).__init__(
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

    def is_service_healthy(self, timeout=2, payload=None, packet_size=0):
        status = super(SMTPAgent, self).is_service_healthy()
        port_open = is_port_open(
            port=self.config.get('port'),
            ip=self.ip,
            protocol=self.protocol,
            logger=self.logger,
            timeout=timeout,
            payload=payload,
            packet_size=packet_size
        )
        return status and port_open and bool(self.check_banner())

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
        protocol='tcp',
        command_queue_size=0,
        config=None
    ):
        if config is None:
            config = Config(name='smtp_postfix', protocol=protocol)
        elif isinstance(config, dict):
            config.setdefault('name', 'smtp_postfix')
            config.setdefault('protocol', protocol)
            config = Config.from_dict(config)
        elif isinstance(config, Config):
            if not config.name:
                config.name = 'smtp_postfix'
            if not getattr(config, 'protocol', None):
                config.protocol = protocol

        super(SMTPAgentPostfix, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )
