import json
import logging
import os

import urllib2

from ..agent import ServerAgent
from ..utils.helpers import restart_service
from ..utils.logtools import maybe_log_message


class WebAgent(ServerAgent):
    """
    Agent for monitoring web server health and status.
    """

    def __init__(
        self,
        server_name='web',
        port=None,
        processes=None,
        critical_processes=None,
        interface=None,
        protocol='tcp',
        whitelist_commands=None,
        server_host=None,
    ):
        port = int(self._get_env_or_param(port, 'PORT'))

        super(WebAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['gunicorn', 'uvicorn', 'nginx'],
            critical_processes=critical_processes,
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
        )

        self.server_host = self._get_env_or_param(server_host, 'SERVER_HOST')
        self.health_url = self._build_url('health')

    def is_service_healthy(
            self, timeout=2, payload=None, packet_size=0
    ):
        """
        Check if the web service is healthy.

        Makes an HTTP request to the health endpoint and verifies:
        1. The response JSON contains status="ok"
        2. The port is open and accessible
        3. The parent class's health check passes

        Args:
            timeout (int, optional): Request timeout in seconds. Defaults to 2.
            payload (str, optional): Payload for the request. Defaults to None.
            packet_size (int, optional): Size of the packet. Defaults to 0.

        Returns:
            bool: True if the service is healthy, False otherwise.
        """
        try:
            request = urllib2.Request(self.health_url)
            response = urllib2.urlopen(request, timeout=timeout)

            if not (200 <= response.getcode() < 300):
                maybe_log_message(
                    'Server responded with status code %d' % (
                        response.getcode()
                    ),
                    self.logger,
                    self.fallback_logger
                )
                return False

            response_data = json.loads(response.read())
            if 'status' not in response_data:
                maybe_log_message(
                    'Health check failed: Response missing status key',
                    self.logger,
                    self.fallback_logger
                )
                return False

            server_health_status = response_data['status']
            if server_health_status != 'ok':
                maybe_log_message(
                    'Health check failed: Server status is %s' % (
                        server_health_status
                    ),
                    self.logger,
                    self.fallback_logger
                )
                return False

            status = super(WebAgent, self).is_service_healthy()
            return status and self.is_port_open(
                timeout=timeout, payload=payload, packet_size=packet_size
            )
        except Exception as e:
            maybe_log_message(
                'Health check failed with error: %s' % str(e),
                self.logger,
                self.fallback_logger
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
        return 'http://%s:%d/%s' % (self.server_host, self.port, endpoint)

    def _get_env_or_param(self, param_value, env_name):
        """
        Get value from parameter or environment variable.

        Args:
            param_value: Value passed as parameter
            env_name (str): Name of environment variable

        Returns:
            The parameter value if provided, otherwise environment variable

        Raises:
            ValueError: If neither parameter nor environment variable is set
        """
        if param_value is None and env_name not in os.environ:
            raise ValueError('%s environment variable is not set.' % env_name)
        return param_value or os.environ[env_name]
