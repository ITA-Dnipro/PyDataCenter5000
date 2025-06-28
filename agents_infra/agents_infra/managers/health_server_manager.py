import logging
import threading

from BaseHTTPServer import HTTPServer

from ..utils.health_http import HealthHandler
from ..utils.logtools import maybe_log_message
from .base import ServerManager


class HealthServerManager(ServerManager):
    def __init__(self, agent, port=None):
        self.agent = agent
        self.port = port if port is not None else agent.health_port
        self.server = None
        self.thread = None

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent.server_name, 'health-server'])
        )

    def start(self):
        def run():
            try:
                self.server = HTTPServer(('', self.port), HealthHandler)
                self.server.server_name = self.agent.server_name
                self.server.uptime = self.agent.uptime
                self.server.is_service_healthy_callback = (
                    self.agent.is_service_healthy
                )

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
        if self.server is not None:
            maybe_log_message(
                'Shutting down health server...',
                logger=self.logger,
                level=logging.INFO
            )
            try:
                self.server.shutdown()
                self.server.server_close()
                self.thread.join()

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
                del self.server
                del self.thread
