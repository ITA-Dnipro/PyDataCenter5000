import subprocess

from agents.agent import ServerAgent
from agents.utils.logtools import maybe_log_message


class DNSAgent(ServerAgent):

    def __init__(
        self,
        server_name='dns',
        port=53,
        processes=None,
        interface='enp0s3',
        controller_url=None,
    ):
        super(DNSAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['named', 'bind9'],
            interface=interface,
            controller_url=controller_url,
        )

    def is_dns_running(self):
        """
        Check if DNS is responding to queries using dig.
        Returns:
            bool: True if DNS query succeeds, False otherwise.
        """
        try:
            # Run the dig command
            process = subprocess.Popen(
                ['dig', '@localhost', 'google.com', '+short'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output, error = process.communicate()

            if process.returncode != 0:
                return False

            # If output is not empty, DNS is working
            return bool(output.strip())

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
