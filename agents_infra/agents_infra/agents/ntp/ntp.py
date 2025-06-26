import logging

from ...utils.helpers import restart_service
from ...utils.logtools import maybe_log_message
from ..base import ServerAgent


class NTPAgent(ServerAgent):

    def __init__(
        self,
        server_name='ntp',
        port=123,
        processes=None,
        critical_processes=None,
        interface='enp0s3',
        protocol='udp',
        whitelist_commands=None,
    ):
        super(NTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['ntpd', 'chronyd', 'systemd-timesyncd'],
            critical_processes=critical_processes,
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
        )

    def service_healthy(
        self, timeout=2, payload=b'\x1b' + 47 * b'\0', packet_size=48
    ):
        status = super(NTPAgent, self).is_service_healthy()
        return status and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )

    def maybe_restart_service(self):
        inactive_services = []

        if not self.is_ssh_service_active():
            inactive_services.append('ssh')

        if inactive_services:
            for service in inactive_services:
                restart_service(self.logger, self.fallback_logger, service)

            maybe_log_message(
                'Finished attempts to restart services',
                self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.INFO
                )
            return False

        maybe_log_message(
            'All services are heathy and running',
            self.logger,
            fallback_logger=self.fallback_logger,
            level=logging.INFO
            )
        return True
