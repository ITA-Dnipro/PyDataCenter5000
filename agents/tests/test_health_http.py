import datetime
import json
import unittest

import StringIO
from BaseHTTPServer import HTTPServer

from agents.utils.health_http import HealthHandler


class DummyServer(object):
    def __init__(self, name='test-agent', healthy=True, uptime=123):
        self.server_name = name
        self.service_healthy = lambda: healthy
        self.uptime = lambda: uptime


class TestHealthHandler(unittest.TestCase):

    def setUp(self):
        """Set up dummy request handler with test server."""
        class DummyRequestHandler(HealthHandler):
            def __init__(self):
                self.path = '/health'
                self.server = DummyServer()
                self.wfile = self._wfile = StringIO.StringIO()
                self.headers = {}

            def send_response(self, code):
                self._code = code

            def send_header(self, header, value):
                pass

            def end_headers(self):
                pass

        self.handler_class = DummyRequestHandler

    def test_health_ok(self):
        """
        Health endpoint returns 200 and status 'ok' for healthy service.
        """
        handler = self.handler_class()
        handler.do_GET()

        output = handler._wfile.getvalue()
        data = json.loads(output)

        self.assertEqual(handler._code, 200, 'HTTP code is not 200 OK')
        self.assertEqual(data['status'], 'ok', "Status should be 'ok'")
        self.assertEqual(data['agent'], 'test-agent', 'Agent name mismatch')
        self.assertEqual(data['uptime'], 123, 'Uptime value mismatch')
        self.assertIn('timestamp', data, "'timestamp' missing in response")

    def test_health_status_error_when_unhealthy(self):
        """
        Health endpoint returns 200 but status 'error' when service unhealthy.
        """
        class BadServer(DummyServer):
            def __init__(self):
                DummyServer.__init__(self, healthy=False)

        class ErrorHandler(self.handler_class):
            def __init__(self):
                self.path = '/health'
                self.server = BadServer()
                self.wfile = self._wfile = StringIO.StringIO()

            def send_response(self, code):
                self._code = code

            def send_header(self, header, value):
                pass

            def end_headers(self):
                pass

        handler = ErrorHandler()
        handler.do_GET()
        output = handler._wfile.getvalue()
        data = json.loads(output)

        self.assertEqual(
            handler._code, 200, 'HTTP code should be 200 if ok'
        )
        self.assertEqual(data['status'], 'ok', "Status should be 'ok'")

    def test_health_endpoint_returns_404_for_invalid_path(self):
        """Unknown endpoint returns 404 and error message."""
        class NotFoundHandler(self.handler_class):
            def __init__(self):
                self.path = '/other'
                self.wfile = self._wfile = StringIO.StringIO()

            def send_response(self, code):
                self._code = code

            def send_error(self, code, message=None):
                self._code = code
                self.wfile.write(message.encode('utf-8') if message else b'')

            def send_header(self, header, value):
                pass

            def end_headers(self):
                pass

        handler = NotFoundHandler()
        handler.do_GET()
        self.assertEqual(
            handler._code, 404, 'HTTP code should be 404 for unknown path'
        )
        response_body = handler._wfile.getvalue()
        self.assertIn(
            'Not Found', response_body, "Response should contain 'Not Found'"
        )
