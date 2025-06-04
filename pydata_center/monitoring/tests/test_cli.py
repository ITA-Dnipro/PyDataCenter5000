import sys
import time
import unittest
from io import StringIO
from unittest.mock import Mock, patch

import requests
from cli.controller_cli import list_agents, poll_result, send_command, truncate


class TestListAgents(unittest.TestCase):
    def test_truncate_func(self):
        test_cases = [
            ('Lorem ipsum', 10, 'Lorem i...'),
            ('Lorem ipsum', 15, 'Lorem ipsum'),
            ('Lorem ipsum', 3, '...')
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
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        list_agents(username='admin', password='adminpass')

        sys.stdout = sys.__stdout__

        output = captured_output.getvalue()
        self.assertIn('Ubuntu-Server-001', output)
        self.assertIn('Debian-Server-002', output)
        self.assertIn('Kyiv-Server-001', output)
        self.assertIn('Lviv-Server-002', output)


class TestSendCommand(unittest.TestCase):
    @patch('cli.controller_cli.requests.post')
    def test_send_command_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {'command_id': 123}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        command_id = send_command(
            agent_hostname='TestAgent',
            command='echo Hello',
            username='user',
            password='pass'
        )

        sys.stdout = sys.__stdout__

        self.assertEqual(command_id, 123)
        self.assertIn(
            'Command sent to TestAgent successfully. Command ID: 123',
            captured_output.getvalue()
        )

    @patch('cli.controller_cli.requests.post')
    def test_send_command_no_id(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        command_id = send_command(
            agent_hostname='TestAgent',
            command='ls -la',
            username='user',
            password='pass'
        )

        sys.stdout = sys.__stdout__

        self.assertIsNone(command_id)
        self.assertIn(
            'Command sent, but no command ID returned.',
            captured_output.getvalue()
        )

    @patch('cli.controller_cli.requests.post')
    def test_send_command_http_error(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            '500 Server Error'
        )
        mock_post.return_value = mock_response

        captured_output = StringIO()
        sys.stdout = captured_output

        command_id = send_command('Host', 'cmd', 'user', 'pass')

        sys.stdout = sys.__stdout__

        self.assertIsNone(command_id)
        self.assertIn(
            'HTTP error occurred: 500 Server Error',
            captured_output.getvalue()
        )

    @patch(
        'cli.controller_cli.requests.post',
        side_effect=requests.RequestException('Request error')
    )
    def test_send_command_request_exception(self, mock_post):
        captured_output = StringIO()
        sys.stdout = captured_output

        command_id = send_command('Host', 'cmd', 'user', 'pass')

        sys.stdout = sys.__stdout__

        self.assertIsNone(command_id)
        self.assertIn(
            'Request failed: Request error',
            captured_output.getvalue()
        )

    @patch(
        'cli.controller_cli.requests.post',
        side_effect=Exception('Unknown error')
    )
    def test_send_command_unexpected_exception(self, mock_post):
        captured_output = StringIO()
        sys.stdout = captured_output

        command_id = send_command('Host', 'cmd', 'user', 'pass')

        sys.stdout = sys.__stdout__

        self.assertIsNone(command_id)
        self.assertIn(
            'Unexpected error: Unknown error',
            captured_output.getvalue()
        )


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
