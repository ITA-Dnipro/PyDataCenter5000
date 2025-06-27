import json
import logging
import unittest

import mock
import StringIO

from agents_infra.agents_infra.managers.health_server_manager import \
    HealthServerManager
from agents_infra.agents_infra.utils.health_http import HealthHandler


class DummyServer(object):
    def __init__(self, name='test-agent', healthy=True, uptime=123):
        self.server_name = name
        self.is_service_healthy = lambda: healthy
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
        self.assertTrue('timestamp' in data, "'timestamp' missing in response")

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
            handler._code, 200, 'HTTP code should be 200 if service unhealhy'
        )
        self.assertEqual(data['status'], 'error', "Status should be 'error'")

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
        self.assertTrue(
            'Not Found' in response_body, "Response should contain 'Not Found'"
        )

    def test_health_status_error_on_exception(self):
        """
        Health endpoint returns 500 with status 'error' and error message
        when uptime() or is_service_healthy() raises an exception.
        """
        class FailingServer(DummyServer):
            def __init__(self):
                super(FailingServer, self).__init__()

                def fail():
                    return 1 / 0
                self.uptime = fail

        class FailingHandler(self.handler_class):
            def __init__(self):
                self.path = '/health'
                self.server = FailingServer()
                self.wfile = self._wfile = StringIO.StringIO()

            def send_response(self, code):
                self._code = code

            def send_header(self, header, value):
                pass

            def end_headers(self):
                pass

        handler = FailingHandler()
        handler.do_GET()
        output = handler._wfile.getvalue()
        data = json.loads(output)

        self.assertEqual(
            handler._code,
            500,
            'HTTP code should be 500 while exception is raised'
        )
        self.assertEqual(data['status'], 'error', "Status should be 'error'")
        self.assertTrue(
            'message' in data, "Response should contain an error 'message'"
        )


class TestHealthServerManager(unittest.TestCase):
    @mock.patch('agents_infra.managers.health_server_manager.HTTPServer')
    def test_stop_calls_shutdown_and_server_close(self, mock_httpserver_cls):
        manager = HealthServerManager(
            agent_name='test',
            is_service_healthy_callback=lambda: True
        )

        mock_server = mock.Mock()
        mock_thread = mock.Mock()
        manager.health_server = mock_server
        manager.health_thread = mock_thread

        manager.stop()

        self.assertTrue(
            mock_server.shutdown.called,
            'shutdown() was not called on the server'
            )
        self.assertTrue(
            mock_server.server_close.called,
            'server_close() was not called on the server'
        )
        self.assertTrue(
            mock_thread.join.called,
            'join() was not called on the thread'
        )

    def test_logger_initialized(self):
        agent_name = 'test'
        manager = HealthServerManager(
            agent_name=agent_name,
            is_service_healthy_callback=lambda: True
        )

        logger = manager.logger
        expected_logger_name = '%s-health-server' % agent_name

        self.assertTrue(isinstance(logger, logging.Logger))
        self.assertEqual(logger.name, expected_logger_name)
