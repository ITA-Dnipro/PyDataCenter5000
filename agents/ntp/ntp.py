import logging

from ..agent import ServerAgent
from ..utils.helpers import restart_service
from ..utils.logtools import maybe_log_message


class NTPAgent(ServerAgent):
    """
    Agent subclass for monitoring and managing an NTP daemon.
    """

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
        """
        Check both the NTP process health and UDP port responsiveness.
        Returns True only if both are OK.
        """
        base_ok = super(NTPAgent, self).is_service_healthy()
        port_ok = self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
        return base_ok and port_ok

    def maybe_restart_service(self):
        """
        Check NTP and SSH services; if any are inactive, attempt restart.
        Returns True if all services are healthy (or successfully restarted),
        False if one failed to restart.
        """
        inactive_services = []

        # SSH health
        if not self.is_ssh_service_active():
            inactive_services.append('ssh')

        # NTP health
        ntp_running = any(
            self._is_process_running(proc_name=proc)
            for proc in self.critical_processes or []
        )
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

        # Attempt restarts
        ssh_ok = self.is_ssh_service_active()
        ntp_ok = any(
            self._is_process_running(proc_name=proc)
            for proc in self.critical_processes or []
        )
        services_str = ', '.join(inactive_services)
        if ssh_ok and ntp_ok:
            maybe_log_message(
                'Services recovered after restart: {}'.format(services_str),
                self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.INFO
            )
            return True
        else:
            maybe_log_message(
                'Restart attempts finished but some services still down: {}'
                .format(services_str),
                self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.ERROR
            )
            return False
