import unittest
import datetime
import json
import StringIO

from BaseHTTPServer import HTTPServer
from utils.health_http import HealthHandler


class DummyServer(object):
    def __init__(self, name='test-agent', healthy=True, uptime=123):
        self.server_name = name
        self.service_healthy = lambda: healthy
        self.uptime = lambda: uptime


class TestHealthHandler(unittest.TestCase):

    def setUp(self):
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
        handler = self.handler_class()
        handler.do_GET()

        output = handler._wfile.getvalue()
        data = json.loads(output)

        self.assertEqual(handler._code, 200, "HTTP code is not 200 OK")
        self.assertEqual(data['status'], 'ok', "Status should be 'ok'")
        self.assertEqual(data['agent'], 'test-agent', "Agent name mismatch")
        self.assertEqual(data['uptime'], 123, "Uptime value mismatch")
        self.assertTrue('timestamp' in data, "'timestamp' missing in response")

    def test_health_service_error(self):
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

        self.assertEqual(handler._code, 200, "HTTP code should be 200 even if error")
        self.assertEqual(data['status'], 'error', "Status should be 'error'")

    def test_not_found(self):
        class NotFoundHandler(self.handler_class):
            def __init__(self):
                self.path = '/other'
                self.wfile = self._wfile = StringIO.StringIO()

            def send_response(self, code):
                self._code = code

            def end_headers(self):
                pass

        handler = NotFoundHandler()
        handler.do_GET()
        self.assertEqual(handler._code, 404, "HTTP code should be 404 for unknown path")
