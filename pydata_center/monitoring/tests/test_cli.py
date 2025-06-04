import sys
import time
import unittest
from io import StringIO
from unittest.mock import Mock, patch

import requests
from cli.controller_cli import list_agents, poll_result, truncate


class TestListAgents(unittest.TestCase):
    def test_truncate_func(self):
        test_cases = [
            ('Lorem ipsum', 10, 'Lorem i...'),
            ('Lorem ipsum', 15, 'Lorem ipsum'),
            ('Lorem ipsum', 3, '...'),
        ]
        for text, max_len, expected in test_cases:
            with self.subTest(text=text, max_len=max_len):
                self.assertEqual(truncate(text, max_len), expected)

    @patch('cli.controller_cli.requests.get')
    def test_list_agents_with_mocked_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'id': 1,
                'hostname': 'Ubuntu-Server-001',
                'server_name': 'Kyiv-Server-001'
            },
            {
                'id': 2,
                'hostname': 'Debian-Server-002',
                'server_name': 'Lviv-Server-002'
            }
        ]
        mock_get.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        list_agents()

        sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('Ubuntu-Server-001', output)
        self.assertIn('Debian-Server-002', output)
        self.assertIn('Kyiv-Server-001', output)
        self.assertIn('Lviv-Server-002', output)


class TestPollResult(unittest.TestCase):

    @patch('cli.controller_cli.requests.patch')
    def test_result_immediately_available(self, mock_patch):
        mock_response = Mock()
        mock_response.json.return_value = {'result': 'success'}
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        result = poll_result(command_id=1, interval=1, timeout=5)

        sys.stdout = sys.__stdout__

        self.assertEqual(result, {'result': 'success'})
        self.assertNotIn('Waiting for result...', captured_output.getvalue())
        self.assertNotIn('Timeout', captured_output.getvalue())

    @patch('cli.controller_cli.requests.patch')
    def test_status_done(self, mock_patch):
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'done'}
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        result = poll_result(command_id=2, interval=1, timeout=5)

        sys.stdout = sys.__stdout__

        self.assertEqual(result, {'status': 'done'})
        self.assertNotIn('Waiting for result...', captured_output.getvalue())
        self.assertNotIn('Timeout', captured_output.getvalue())

    @patch('cli.controller_cli.requests.patch')
    def test_timeout_reached(self, mock_patch):
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'pending'}
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        result = poll_result(command_id=3, interval=1, timeout=2)

        sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('Waiting for result...', output)
        self.assertIn('Timeout after 2 seconds.', output)
        self.assertEqual(result, {'status': 'pending'})

    @patch(
        'cli.controller_cli.requests.patch',
        side_effect=requests.ConnectionError('Connection error')
    )
    def test_request_exception(self, mock_patch):
        captured_output = StringIO()
        sys.stdout = captured_output

        result = poll_result(command_id=4, interval=1, timeout=2)

        sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('Request failed: Connection error', output)
        self.assertIsNone(result)
