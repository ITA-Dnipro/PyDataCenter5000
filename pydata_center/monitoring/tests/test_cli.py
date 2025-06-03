import sys
import unittest
from io import StringIO
from unittest.mock import Mock, patch

from cli.controller_cli import list_agents, truncate


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
