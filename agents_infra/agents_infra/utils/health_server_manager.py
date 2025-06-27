import logging
import threading

from BaseHTTPServer import HTTPServer

from ..utils.health_http import HealthHandler
from .logtools import maybe_log_message


class HealthServerManager:
    def __init__(
            self,
            agent_name,
            is_service_healthy_callback,
            port=8081,
            uptime_callback=None
    ):
        self.agent_name = agent_name
        self.is_service_healthy = is_service_healthy_callback
        self.port = port
        self.uptime_callback = uptime_callback or (lambda: None)
        self.server = None
        self.thread = None

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent_name, 'health-server'])
        )

    def start(self):
        def run():
            try:
                self.server = HTTPServer(('', self.port), HealthHandler)
                self.server.server_name = self.agent_name
                self.server.uptime = self.uptime_callback
                self.server.is_service_healthy = self.is_service_healthy

                maybe_log_message(
                    'Health server running at /health on port %s' % self.port,
                    logger=self.logger,
                    level=logging.INFO
                )
                self.server.serve_forever()
            except Exception as e:
                maybe_log_message(
                    'Failed to start health server: %s' % e,
                    logger=self.logger,
                    exc_info=True
                )

        self.thread = threading.Thread(target=run, name='HealthServerThread')
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        if hasattr(self, 'health_server'):
            maybe_log_message(
                'Shutting down health server...',
                logger=self.logger,
                level=logging.INFO
            )
            try:
                self.health_server.shutdown()
                self.health_server.server_close()
                self.health_thread.join()

                maybe_log_message(
                    'Health server shut down successfully.',
                    logger=self.logger,
                    level=logging.INFO
                )
            except Exception as e:
                maybe_log_message(
                    'Failed to shut down health server: %s' % e,
                    logger=self.logger,
                    level=logging.ERROR
                )
            finally:
                del self.health_server
                del self.health_thread
