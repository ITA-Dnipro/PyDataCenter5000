import abc
import json
import logging

import urllib2

from ...utils.configtools import Config
from ...utils.helpers import get_env_or_param
from ...utils.sysinfo import is_port_open
from ..base import ServerAgent


class WebAgent(ServerAgent):
    """
    Agent for monitoring web server health and status.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        protocol='tcp',
        command_queue_size=0,
        config=None
    ):

        # If not config - set default
        if config is None:
            config = Config(name='web', protocol=protocol)
        elif isinstance(config, dict):
            config = Config.from_dict(config)

        super(WebAgent, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

        self.web_server_port = int(get_env_or_param(
            self.config.get('port'),
            'PORT'
            ))

        self.web_server_host = get_env_or_param(
            self.config.get('web_server_host'),
            'WEB_SERVER_HOST'
        )
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
            return status and is_port_open(
                port=self.web_server_port,
                ip=self.ip,
                protocol=self.protocol,
                logger=self.logger,
                timeout=timeout,
                payload=payload,
                packet_size=packet_size
            )
        except Exception as e:
            self.log_with_controller(
                'Health check failed with error: %s' % str(e),
                level=logging.ERROR,
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
                self.log_with_controller(
                    'Server responded with status code %d' % (
                        response.getcode()
                    ),
                    level=logging.WARNING,
                )
                return False

            response_data = json.loads(response.read())
            if 'status' not in response_data:
                self.log_with_controller(
                    'Health check failed: Response missing status key',
                    level=logging.WARNING,
                )
                return False

            server_health_status = response_data['status']
            if server_health_status != 'ok':
                self.log_with_controller(
                    'Health check failed: Server status is %s' % (
                        server_health_status
                    ),
                    level=logging.WARNING,
                )
                return False

            return True
        except Exception as e:
            self.log_with_controller(
                'HTTP health check failed with error: %s' % str(e),
                level=logging.ERROR,
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
            self.web_server_host, self.web_server_port, endpoint
        )


class WebAgentFastapi(WebAgent):
    """
    Agent subclass for monitoring Uvicorn web server health and status.
    """
    def __init__(
        self,
        protocol='tcp',
        command_queue_size=0,
        config=None
    ):
        # Setting ='web_fastapi' if not provided
        if config is None:
            config = Config(name='web_fastapi', protocol=protocol)
        elif isinstance(config, dict):
            config = Config.from_dict(config)

        super(WebAgentFastapi, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )
