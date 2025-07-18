import abc
import logging
import subprocess

from ...utils.configtools import Config
from ...utils.helpers import is_valid_ip
from ...utils.sysinfo import is_port_open
from ..base import ServerAgent


class DNSAgent(ServerAgent):

    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        protocol='udp',
        command_queue_size=0,
        config=None
    ):
        # If not config - set default
        if config is None:
            config = Config(name='dns', protocol=protocol)
        elif isinstance(config, dict):
            config = Config.from_dict(config)

        super(DNSAgent, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
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
            self.log_with_controller(
                'DNS check failed: %s' % e,
                level=logging.ERROR,
                exc_info=True,
            )
            return False

    def is_service_healthy(self, timeout=2, payload=None, packet_size=0):
        process_status = super(DNSAgent, self).is_service_healthy()
        port = is_port_open(
            port=self.config.get('port'),
            ip=self.ip,
            protocol=self.protocol,
            logger=self.logger,
            timeout=timeout,
            payload=payload,
            packet_size=packet_size
        )
        dns_status = self.is_dns_running()

        return process_status and port and dns_status


class DNSAgentNamed(DNSAgent):
    """
    DNSAgentNamed is a specialized subclass of DNSAgent designed to monitor
    and manage a DNS server running with the 'named' process.
    """

    def __init__(
        self,
        protocol='udp',
        command_queue_size=0,
        config=None
    ):
        # Setting ='dns_named' if not provided
        if config is None:
            config = Config(name='dns_named', protocol=protocol)
        elif isinstance(config, dict):
            config = Config.from_dict(config)

        super(DNSAgentNamed, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )
