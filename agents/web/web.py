import json
import logging

import urllib2

from ..agent import ServerAgent
from ..utils.helpers import get_env_or_param, restart_service
from ..utils.logtools import maybe_log_message


class WebAgent(ServerAgent):
    """
    Agent for monitoring web server health and status.
    """

    def __init__(
        self,
        server_name='web',
        protocol='tcp',
        command_queue_size=0,
        config=None,
        web_server_host=None,
        web_server_name=None,
    ):
        super(WebAgent, self).__init__(
            server_name=server_name,
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

        self.web_server_host = get_env_or_param(web_server_host,
                                                'WEB_SERVER_HOST')
        self.web_server_name = get_env_or_param(web_server_name,
                                                'WEB_SERVER_NAME')
        self.health_url = self._build_url('health')

        self.web_server_host = get_env_or_param(web_server_host,
                                                'WEB_SERVER_HOST')
        self.web_server_name = get_env_or_param(web_server_name,
                                                'WEB_SERVER_NAME')
        self.health_url = self._build_url('health')

    def is_service_healthy(
            self, timeout=2, payload=None, packet_size=0
    ):
        """
        Check if the web service is healthy.

        Returns:
            bool: True if the service is healthy, False otherwise.
        """
        try:
            if not self._check_http_health(timeout):
                return False

            status = super(WebAgent, self).is_service_healthy()
            return status and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
        except Exception as e:
            maybe_log_message(
                'Health check failed with error: %s' % str(e),
                logger=self.logger,
            )
            return False

    def _check_http_health(self, timeout=2):
        """
        Make an HTTP request to the health endpoint and check the response.

        Returns:
            bool: True if the HTTP health check passes, False otherwise.
        """
        try:
            request = urllib2.Request(self.health_url)
            response = urllib2.urlopen(request, timeout=timeout)

            if not (200 <= response.getcode() < 300):
                maybe_log_message(
                    'Server responded with status code %d' % (
                        response.getcode()
                    ),
                    logger=self.logger,
                )
                return False

            response_data = json.loads(response.read())
            if 'status' not in response_data:
                maybe_log_message(
                    'Health check failed: Response missing status key',
                    self.logger,
                )
                return False

            server_health_status = response_data['status']
            if server_health_status != 'ok':
                maybe_log_message(
                    'Health check failed: Server status is %s' % (
                        server_health_status
                    ),
                    self.logger,
                )
                return False

            return True
        except Exception as e:
            maybe_log_message(
                'HTTP health check failed with error: %s' % str(e),
                self.logger,
            )
            return False

    def _build_url(self, endpoint):
        """
        Build the full URL for a given endpoint.

        Args:
            endpoint (str): The API endpoint to call

        Returns:
            str: The complete URL including host, port and endpoint
        """
        return 'http://%s:%d/%s' % (
            self.web_server_host, self.config.get('port'), endpoint
        )

    def maybe_restart_service(self):
        inactive_services = []

        if not self.is_ssh_service_active():
            inactive_services.append('ssh')

        if not self._check_http_health():
            inactive_services.append(self.web_server_name)

        if inactive_services:
            for service in inactive_services:
                restart_service(service, logger=self.logger)

            maybe_log_message(
                'Finished attempts to restart services',
                logger=self.logger,
                level=logging.INFO,
            )
            return False

        maybe_log_message(
            'All services are healthy and running',
            logger=self.logger,
            level=logging.INFO,
        )
        return True
