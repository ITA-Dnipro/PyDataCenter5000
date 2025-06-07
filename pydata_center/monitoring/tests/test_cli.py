import sys
import time
import unittest
from io import StringIO
from unittest.mock import Mock, patch

import requests
from cli.controller_cli import (handle_agents, handle_login, handle_poll,
                                handle_send, list_agents, poll_result,
                                send_command, truncate)


class TestTruncateFunction(unittest.TestCase):
    """Tests for the truncate() utility function
    with different text lengths and edge cases."""

    def test_truncate_func(self):
        test_cases = [
            ('Lorem ipsum', 10, 'Lorem i...'),
            ('Lorem ipsum', 15, 'Lorem ipsum'),
            ('Lorem ipsum', 3, '...'),
            ('', 10, ''),
            ('A', 0, ''),
            ('A', 1, 'A'),
            ('A', 2, 'A'),
            ('A', 3, 'A'),
            ('Hello world', 0, ''),
        ]
        for text, max_len, expected in test_cases:
            with self.subTest(text=text, max_len=max_len):
                self.assertEqual(
                    truncate(text, max_len),
                    expected,
                    msg=(
                        f"Expected truncated '{text}' to be '{expected}' "
                        f'with max_len={max_len}'
                    )
                )

    def test_truncate_negative_max_length_raises(self):
        with self.assertRaises(ValueError):
            truncate('Hello', -1)


class TestListAgents(unittest.TestCase):
    """Tests for the list_agents() function and its output formatting."""

    @patch('cli.controller_cli.requests.get')
    def test_list_agents_with_mocked_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'id': 1,
                'hostname': 'Ubuntu-Server-001',
            },
            {
                'id': 2,
                'hostname': 'Debian-Server-002',
                'server_name': 'Lviv-Server-002'
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='INFO') as log:
            list_agents(username='admin', password='adminpass')

        log_output = '\n'.join(log.output)
        self.assertIn('Ubuntu-Server-001', log_output)
        self.assertIn('Debian-Server-002', log_output)
        self.assertIn('Lviv-Server-002', log_output)


class TestSendCommand(unittest.TestCase):
    """Tests for the send_command() function
    including success, error, and edge cases."""

    @patch('cli.controller_cli.requests.post')
    def test_send_command_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {'command_id': 123}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='INFO') as log:
            command_id = send_command(
                'TestAgent', 'echo Hello', 'user', 'pass'
            )

        self.assertEqual(command_id, 123)
        self.assertIn(
            'Command sent to TestAgent successfully. Command ID: 123',
            '\n'.join(log.output)
        )

    @patch('cli.controller_cli.requests.post')
    def test_send_command_no_id(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='WARNING') as log:
            command_id = send_command(
                'TestAgent', 'ls -la', 'user', 'pass'
            )

        self.assertIsNone(command_id)
        self.assertIn(
            'Command sent, but no command ID returned.', '\n'.join(log.output)
        )

    @patch('cli.controller_cli.requests.post')
    def test_send_command_http_error(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            '500 Server Error'
        )
        mock_post.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='ERROR') as log:
            command_id = send_command('Host', 'cmd', 'user', 'pass')

        self.assertIsNone(command_id)
        self.assertIn(
            'HTTP error occurred: 500 Server Error', '\n'.join(log.output)
        )

    @patch(
        'cli.controller_cli.requests.post',
        side_effect=requests.RequestException('Request error')
    )
    def test_send_command_request_exception(self, mock_post):
        with self.assertLogs('cli.controller_cli', level='ERROR') as log:
            command_id = send_command('Host', 'cmd', 'user', 'pass')

        self.assertIsNone(command_id)
        self.assertIn('Request failed: Request error', '\n'.join(log.output))

    @patch(
        'cli.controller_cli.requests.post',
        side_effect=Exception('Unknown error')
    )
    def test_send_command_unexpected_exception(self, mock_post):
        with self.assertLogs('cli.controller_cli', level='ERROR') as log:
            command_id = send_command('Host', 'cmd', 'user', 'pass')

        self.assertIsNone(command_id)
        self.assertIn('Unexpected error: Unknown error', '\n'.join(log.output))


class TestPollResult(unittest.TestCase):
    """Tests for the poll_result() function
    covering available, pending, and error scenarios."""

    @patch('cli.controller_cli.requests.patch')
    def test_result_immediately_available(self, mock_patch):
        mock_response = Mock()
        mock_response.json.return_value = {'result': 'success'}
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='INFO') as log:
            result = poll_result(
                command_id=1,
                interval=1,
                timeout=5,
                username='admin',
                password='adminpass'
            )

        self.assertEqual(result, {'result': 'success'})
        output = '\n'.join(log.output)
        self.assertNotIn('Waiting for result...', output)
        self.assertNotIn('Timeout', output)

    @patch('cli.controller_cli.requests.patch')
    def test_status_done(self, mock_patch):
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'done'}
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='INFO') as log:
            result = poll_result(
                command_id=2,
                interval=1,
                timeout=5,
                username='admin',
                password='adminpass'
            )

        self.assertEqual(result, {'status': 'done'})
        output = '\n'.join(log.output)
        self.assertNotIn('Waiting for result...', output)
        self.assertNotIn('Timeout', output)

    @patch('cli.controller_cli.requests.patch')
    def test_timeout_reached(self, mock_patch):
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'pending'}
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        with self.assertLogs('cli.controller_cli', level='WARNING') as log:
            result = poll_result(
                command_id=3,
                interval=1,
                timeout=2,
                username='admin',
                password='adminpass'
            )

        output = '\n'.join(log.output)
        self.assertIn('Timeout after 2 seconds.', output)
        self.assertEqual(result, {'status': 'pending'})

    @patch(
        'cli.controller_cli.requests.patch',
        side_effect=requests.ConnectionError('Connection error')
    )
    def test_request_exception(self, mock_patch):
        with self.assertLogs('cli.controller_cli', level='ERROR') as log:
            result = poll_result(
                command_id=4,
                interval=1,
                timeout=2,
                username='admin',
                password='adminpass'
            )

        output = '\n'.join(log.output)
        self.assertIn('Request failed: Connection error', output)
        self.assertIsNone(result)


class TestHandlers(unittest.TestCase):
    """
    Tests for CLI handlers:
    - handle_login
    - handle_agents
    - handle_send
    - handle_poll
    """

    def setUp(self):
        self.username = 'admin'
        self.password = 'secret'

    @patch('cli.controller_cli.login')
    def test_handle_login_calls_login(self, mock_login):
        args = Mock()
        args.username = self.username
        args.password = self.password

        handle_login(args)
        mock_login.assert_called_once_with(self.username, self.password), (
            'Expected login to be called once with correct credentials'
        )

    @patch('cli.controller_cli.get_auth_from_env',
           return_value=('admin', 'secret'))
    @patch('cli.controller_cli.list_agents')
    def test_handle_agents_calls_list_agents(self,
                                             mock_list_agents,
                                             mock_auth):
        handle_agents()
        mock_list_agents.assert_called_once_with(username='admin',
                                                 password='secret'), (
            'Expected list_agents to be called with correct credentials'
        )

    @patch('cli.controller_cli.get_auth_from_env', return_value=None)
    @patch('cli.controller_cli.logger')
    def test_handle_agents_logs_error_when_not_logged_in(self,
                                                         mock_logger,
                                                         mock_auth):
        handle_agents()
        mock_logger.error.assert_called_once_with(
            "You must login first using the 'login' command."
        ), (
            'Expected error message when not logged in'
        )

    @patch(
        'cli.controller_cli.poll_result', return_value={'result': 'Success'}
    )
    @patch('cli.controller_cli.send_command', return_value='1234')
    @patch('cli.controller_cli.get_auth_from_env',
           return_value=('admin', 'secret'))
    @patch('cli.controller_cli.logger')
    def test_handle_send_with_poll(self,
                                   mock_logger,
                                   mock_auth,
                                   mock_send,
                                   mock_poll):
        args = Mock()
        args.hostname = 'test-host'
        args.cmd = 'ls'
        args.poll = True

        handle_send(args)

        mock_send.assert_called_once(), (
            'Expected send_command to be called once'
        )
        mock_poll.assert_called_once(), (
            'Expected poll_result to be called once'
        )
        mock_logger.info.assert_any_call(
            'Use this ID to poll the result: 1234'
        ), (
            'Expected polling ID log message'
        )
        mock_logger.info.assert_any_call('Result: Success'), (
            'Expected polling result log message'
        )

    @patch('cli.controller_cli.send_command', return_value='1234')
    @patch('cli.controller_cli.get_auth_from_env',
           return_value=('admin', 'secret'))
    @patch('cli.controller_cli.logger')
    def test_handle_send_without_poll(self,
                                      mock_logger,
                                      mock_auth,
                                      mock_send):
        args = Mock()
        args.hostname = 'test-host'
        args.cmd = 'ls'
        args.poll = False

        handle_send(args)

        mock_send.assert_called_once(), (
            'Expected send_command to be called once'
        )
        mock_logger.info.assert_called_once_with(
            'Use this ID to poll the result: 1234'
        ), (
            'Expected log message with polling ID'
        )

    @patch('cli.controller_cli.get_auth_from_env', return_value=None)
    @patch('cli.controller_cli.logger')
    def test_handle_send_logs_error_when_not_logged_in(self,
                                                       mock_logger,
                                                       mock_auth):
        args = Mock()
        args.hostname = 'test-host'
        args.cmd = 'ls'
        args.poll = False

        handle_send(args)

        mock_logger.error.assert_called_once_with(
            "You must login first using the 'login' command."
        ), (
            'Expected error message when not logged in during send'
        )

    @patch('cli.controller_cli.poll_result')
    @patch('cli.controller_cli.get_auth_from_env',
           return_value=('admin', 'secret'))
    def test_handle_poll_calls_poll_result(self,
                                           mock_auth,
                                           mock_poll):
        args = Mock()
        args.id = '1234'
        handle_poll(args)
        mock_poll.assert_called_once_with('1234',
                                          username='admin',
                                          password='secret'), (
            'Expected poll_result to be called with correct ID and credentials'
        )

    @patch('cli.controller_cli.get_auth_from_env', return_value=None)
    @patch('cli.controller_cli.logger')
    def test_handle_poll_logs_error_when_not_logged_in(self,
                                                       mock_logger,
                                                       mock_auth):
        args = Mock()
        args.id = '1234'
        handle_poll(args)
        mock_logger.error.assert_called_once_with(
            "You must login first using the 'login' command."
        ), (
            'Expected error message when not logged in during poll'
        )
