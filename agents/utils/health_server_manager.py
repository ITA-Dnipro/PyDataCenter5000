import logging
import signal
import sys
import threading

from BaseHTTPServer import HTTPServer

from agents.utils.health_http import HealthHandler
from agents.utils.logtools import maybe_log_message

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)


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

        self.logger = logging.getLogger('agents.utils.health_server_manager')
        self.fallback_logger = logging.getLogger(
            'agents.utils.health_server_manager.fallback'
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
                    fallback_logger=self.fallback_logger,
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

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def stop(self):
        if hasattr(self, 'health_server'):
            maybe_log_message(
                'Shutting down health server...',
                logger=self.logger,
                fallback_logger=self.fallback_logger,
                level=logging.INFO
            )
            try:
                self.health_server.shutdown()
                self.health_server.server_close()
                self.health_thread.join()

                maybe_log_message(
                    'Health server shut down successfully.',
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.INFO
                )
            except Exception as e:
                maybe_log_message(
                    'Failed to shut down health server: %s' % e,
                    logger=self.logger,
                    fallback_logger=self.fallback_logger,
                    level=logging.ERROR
                )
            finally:
                del self.health_server
                del self.health_thread

    def _signal_handler(self, signum, frame):
        maybe_log_message(
            'Received signal %s, shutting down...' % signum,
            logger=self.logger,
            fallback_logger=self.fallback_logger,
            level=logging.INFO
        )
        self.stop_health_server()
        sys.exit(0)
