import datetime
import json

from BaseHTTPServer import BaseHTTPRequestHandler


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            try:
                health = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'agent': getattr(self.server, 'server_name', 'unknown'),
                    'uptime': getattr(self.server, 'uptime', lambda: -1)(),
                    'status': 'ok' if getattr(
                        self.server, 'service_healthy_func', lambda: True
                        )() else 'error',
                }
            except Exception as e:
                health = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'agent': getattr(self.server, 'server_name', 'unknown'),
                    'uptime': getattr(
                        self.server, 'uptime', lambda: -1
                        )(),
                    'status': 'error',
                    'message': 'Internal error: %s' % str(e),
                }

            self.wfile.write(json.dumps(health))
        else:
            self.send_response(404)
            self.end_headers()
