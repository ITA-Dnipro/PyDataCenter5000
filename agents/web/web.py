import json
import os

import urllib2

from ..agent import ServerAgent
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
        interface=None,
        protocol='tcp',
        whitelist_commands=None,
        log_path=None,
        server_host=None,
    ):
        if port is None and 'PORT' not in os.environ:
            raise ValueError('PORT environment variable is not set.')

        if server_host is None and 'SERVER_HOST' not in os.environ:
            raise ValueError('SERVER_HOST environment variable is not set.')

        port = port or int(os.environ['PORT'])
        self.server_host = server_host or os.environ['SERVER_HOST']

        super(WebAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['uvicorn'],
            interface=interface,
            protocol=protocol,
            whitelist_commands=whitelist_commands,
            log_path=log_path,
        )

    def _build_url(self, endpoint):
        """
        Build the full URL for a given endpoint.

        Args:
            endpoint (str): The API endpoint to call

        Returns:
            str: The complete URL including host, port and endpoint
        """
        return 'http://%s:%d/%s' % (self.server_host, self.port, endpoint)

    def service_healthy(
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
        request = urllib2.Request(self._build_url('health'))
        response = urllib2.urlopen(request, timeout=timeout)

        if response.getcode() != 200:
            return False

        server_health_status = json.loads(response.read())['status']

        if server_health_status != 'ok':
            maybe_log_message()

        status = super(WebAgent, self).service_healthy()
        return server_health_status == 'ok' and status and self.is_port_open(
            timeout=timeout, payload=payload, packet_size=packet_size
        )
