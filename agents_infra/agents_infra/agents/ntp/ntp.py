import abc

from ...utils.configtools import Config
from ...utils.sysinfo import is_port_open
from ..base import ServerAgent


class NTPAgent(ServerAgent):

    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        protocol='udp',
        command_queue_size=0,
        config=None,
    ):
        # If not config - set default
        if config is None:
            config = Config(name='ntp', protocol=protocol)
        elif isinstance(config, dict):
            config = Config.from_dict(config)

        super(NTPAgent, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

    def is_service_healthy(
        self, timeout=2, payload=b'\x1b' + 47 * b'\0', packet_size=48
    ):
        """
        Check both the NTP process health and UDP port responsiveness.
        Returns True only if both are OK.
        """
        base_ok = super(NTPAgent, self).is_service_healthy()
        port_ok = is_port_open(
            port=self.config.get('port'),
            ip=self.ip,
            protocol=self.protocol,
            logger=self.logger,
            timeout=timeout,
            payload=payload,
            packet_size=packet_size
        )
        return base_ok and port_ok


class NTPAgenttNTPD(NTPAgent):
    """
    Specialized NTPAgent subclass for monitoring the 'ntpd' daemon.

    Inherits all functionality from NTPAgent, configured for 'ntpd'.
    """

    def __init__(
        self,
        protocol='udp',
        command_queue_size=0,
        config=None
    ):
        # Setting ='ntp_ntpd' if not provided
        if config is None:
            config = Config(name='ntp_ntpd', protocol=protocol)
        elif isinstance(config, dict):
            config = Config.from_dict(config)

        super(NTPAgenttNTPD, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )
