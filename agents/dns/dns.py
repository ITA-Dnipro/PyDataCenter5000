import logging
import subprocess

from ..agent import ServerAgent
from ..utils.helpers import is_valid_ip, restart_service
from ..utils.logtools import maybe_log_message


class DNSAgent(ServerAgent):

    def __init__(
        self,
        server_name='dns',
        port=53,
        processes=None,
        interface=None,
        protocol='udp',
        whitelist_commands=None,
        log_path=None,
    ):
        super(DNSAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['named', 'bind9'],
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
            log_path=log_path,
        )

    def run_dig(self, query_domain):
        """
        Run the dig command to query DNS locally.
        Returns:
            tuple: (returncode, stdout, stderr)
        """
        process = subprocess.Popen(
                ['dig', '@localhost', query_domain, '+short'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        output, error = process.communicate()
        return process.returncode, output, error

    def is_dns_running(self):
        """
        Check if DNS is responding to queries using dig.
        Returns:
            bool: True if DNS query succeeds, False otherwise.
        """
        try:
            # Run the dig command
            returncode, output, error = self.run_dig(query_domain='google.com')

            if returncode != 0:
                return False

            # If output is not empty and IP valid, DNS is working
            return bool(output.strip()) and is_valid_ip(output)

        except OSError as e:
            # Command not found or failed to execute
            maybe_log_message(
                'DNS check failed: %s' % e,
                self.logger,
                fallback_logger=self.fallback_logger,
                exc_info=True,
            )
            return False

    def is_service_healthy(self, timeout=2, payload=None, packet_size=0):
        process_status = super(DNSAgent, self).is_service_healthy()
        port = self.is_port_open(
            timeout=timeout, payload=payload, packet_size=packet_size
        )
        dns_status = self.is_dns_running()

        return process_status and port and dns_status

    def maybe_restart_service(self):
        inactive_services = []
        if not self.is_dns_running():
            inactive_services.append('named')

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
