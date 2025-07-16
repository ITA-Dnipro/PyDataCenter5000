import os
import socket
import tempfile

import pytest
from mock import MagicMock, patch

from ...agents.base import ServerAgent
from ...agents.smtp.smtp import SMTPAgent


@pytest.yield_fixture
def smtp_agent():
    """
    Create and configure an SMTPAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    config = {
        'name': 'smtp',
        'port': 25,
        'interface': 'enp0s3',
        'url': 'http://localhost',
        'api_prefix': 'api/v1/',
        'auth_token_type': None,
        'critical_processes': ['postfix', 'sendmail'],
        'whitelist_commands': ['uptime', 'telnet']
    }

    agent = SMTPAgent(config=config)
    agent.setup_logging(logfile.name)

    yield agent, logfile.name

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


@patch.object(SMTPAgent, 'check_banner', return_value='220 Hello')
@patch.object(ServerAgent, 'is_service_healthy', return_value=True)
@patch('agents_infra.agents.smtp.smtp.is_port_open', return_value=True)
def test_service_healthy_true(
    mock_parent_health,
    mock_banner,
    mock_port,
    smtp_agent
):
    """
    Test service_healthy()
    returns truthy value (banner string) when all checks pass
    """
    agent, log_path = smtp_agent
    result = agent.is_service_healthy()
    assert result is True


@patch.object(SMTPAgent, 'check_banner', return_value='')
@patch.object(ServerAgent, 'is_service_healthy', return_value=True)
@patch('agents_infra.agents.smtp.smtp.is_port_open', return_value=True)
def test_service_healthy_fails_due_to_missing_banner(
    mock_parent_health,
    mock_banner,
    mock_port,
    smtp_agent,
):
    """
    Test service_healthy()
    returns empty string (false) if banner is missing
    """
    agent, log_path = smtp_agent
    result = agent.is_service_healthy()
    assert result is False


@patch('agents_infra.agents.smtp.smtp.socket.socket')
def test_check_banner_raises_socket_error(mock_socket, smtp_agent):
    """
    Test that check_banner() returns
    empty string and logs an error
    when socket connection fails
    """
    agent, log_path = smtp_agent

    mock_sock = MagicMock()
    mock_sock.connect.side_effect = socket.error('Mocked socket error')
    mock_sock.close = MagicMock()
    mock_socket.return_value = mock_sock
    agent.ip = '127.0.0.1'

    result = agent.check_banner()

    assert result == ''

    mock_sock.close.assert_called_once()

    with open(log_path, 'r') as f:
        log_content = f.read()

    assert 'mocked socket error' in log_content.lower()
    assert 'error' in log_content.lower()


@patch('agents_infra.agents.smtp.smtp.socket.socket')
def test_check_banner_success(mock_socket, smtp_agent):
    """
    Test that check_banner() successfully reads
    and returns banner string
    """
    agent, log_path = smtp_agent

    mock_sock = MagicMock()
    mock_sock.recv.return_value = b'220 smtp.example.com ESMTP\r\n'
    mock_sock.connect.return_value = None
    mock_sock.close = MagicMock()
    mock_socket.return_value = mock_sock
    agent.ip = '127.0.0.1'

    result = agent.check_banner()

    assert result == '220 smtp.example.com ESMTP'

    mock_sock.close.assert_called_once()
