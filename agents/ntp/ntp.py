import logging

from ..agent import ServerAgent
from ..utils.helpers import restart_service
from ..utils.logtools import maybe_log_message


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

    def is_service_healthy(
        self, timeout=2, payload=b'\x1b' + 47 * b'\0', packet_size=48
    ):
        status = super(NTPAgent, self).is_service_healthy()
        return status and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )

    def maybe_restart_service(self):
        """
        Check NTP and SSH services; if any are inactive, attempt restart.
        Returns True if all services are healthy (or successfully restarted),
        False if one failed to restart.
        """
        inactive_services = []

        # SSH
        if not self.is_ssh_service_active():
            inactive_services.append('ssh')

        # NTP daemons
        # If none of the configured critical_processes are running,
        # treat as down.
        ntp_running = False
        for proc in self.critical_processes:
            self.processes = [proc]
            if self._is_process_running():
                ntp_running = True
                break

        if not ntp_running:
            inactive_services.append('ntp')

        if not inactive_services:
            maybe_log_message(
                'All services are healthy and running',
                self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.INFO
            )
            return True

        for service in inactive_services:
            restart_service(self.logger, self.fallback_logger, service)

        maybe_log_message(
            'Finished attempts to restart services: %s' % ', '
            .join(inactive_services),
            self.logger,
            fallback_logger=self.fallback_logger,
            level=logging.INFO
        )

        return False
