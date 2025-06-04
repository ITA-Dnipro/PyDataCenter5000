import re
import subprocess

from ..agent import ServerAgent
from ..utils.helpers import is_valid_ip
from ..utils.logtools import maybe_log_message


class DNSAgent(ServerAgent):

    def __init__(
        self,
        server_name='dns',
        port=53,
        processes=None,
        interface=None,
        controller_url=None,
        query_domain='google.com'
    ):
        super(DNSAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['named', 'bind9'],
            interface=interface,
            controller_url=controller_url,
        )

        self.query_domain = query_domain

    def run_dig(self):
        """
        Run the dig command to query DNS locally.
        Returns:
            tuple: (returncode, stdout, stderr)
        """
        process = subprocess.Popen(
                ['dig', '@localhost', self.query_domain, '+short'],
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
            returncode, output, error = self.run_dig()

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

    def service_healthy(self):
        return (
            super(DNSAgent, self).service_healthy()
            and self.is_dns_running()
            )
