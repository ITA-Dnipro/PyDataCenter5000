import datetime
import json
import logging

from BaseHTTPServer import BaseHTTPRequestHandler

from .logtools import maybe_log_message

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            try:
                uptime = getattr(self.server, 'uptime', lambda: None)()
                health = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'agent': getattr(self.server, 'server_name', 'unknown'),
                    'uptime': None if uptime == -1 else uptime,
                    'status': 'ok' if getattr(
                        self.server, 'is_service_healthy', lambda: False
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
