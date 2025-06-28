import datetime
import json
import logging

from BaseHTTPServer import BaseHTTPRequestHandler

from .logtools import maybe_log_message

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        Handle GET requests.

        - If path is '/health':
          - Returns HTTP 200 with JSON containing uptime, status
           ('ok' or 'error'), timestamp, and agent name if successful.
          - Returns HTTP 500 with JSON containing error message
          if an exception occurs during status computation.

        - For other paths:
          - Returns HTTP 404 Not Found and logs a warning.
        """
        if self.path == '/health':
            try:
                health = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'agent': getattr(self.server, 'server_name', 'unknown'),
                    'uptime': getattr(self.server, 'uptime', None),
                    'status': 'ok' if getattr(
                        self.server,
                        'is_service_healthy_callback',
                        lambda: False
                    )() else 'error',
                }
                status_code = 200
            except Exception as e:
                maybe_log_message(
                    message=(
                        'Error while generating health check response: %s' % e
                    ),
                    logger=logger,
                    level=logging.ERROR
                )
                health = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'agent': getattr(self.server, 'server_name', 'unknown'),
                    'uptime': None,
                    'status': 'error',
                    'message': 'Internal error: %s' % str(e),
                }
                status_code = 500

            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health))
        else:
            maybe_log_message(
                message='Received unknown path: %s' % self.path,
                logger=logger,
                level=logging.WARNING
            )
            self.send_error(404, 'Not Found')
