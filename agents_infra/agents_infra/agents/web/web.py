import logging
import os

from agents_infra.agents.base import ServerAgent
from agents_infra.utils.helpers import restart_service
from agents_infra.utils.logtools import maybe_log_message


class WebAgent(ServerAgent):

    def __init__(
        self,
        server_name='web',
        port=8000,
        processes=None,
        critical_processes=None,
        interface=None,
        protocol='tcp',
        whitelist_commands=None,
    ):
        if port is None and 'PORT' not in os.environ:
            raise ValueError('WEB port environment variable is not set.')

        port = port or int(os.environ['PORT'])

        super(WebAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['uvicorn'],
            critical_processes=critical_processes,
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
        )

    def is_service_healthy(
            self, timeout=2, payload=None, packet_size=0
    ):
        # TODO: extend health check.
        status = super(WebAgent, self).is_service_healthy()
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
