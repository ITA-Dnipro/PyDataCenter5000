import logging
import logging.handlers
import os
import socket
import tempfile

import pytest
from mock import MagicMock, patch

from agents.agent import ServerAgent
from agents.smtp.smtp import SMTPAgent


@pytest.yield_fixture
def smtp_agent():
    """
    Create and configure a SMTPAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = SMTPAgent()

    logger = logging.getLogger('smtp_agent')
    logger.setLevel(logging.DEBUG)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(logfile.name)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    yield agent, logfile.name

    logger.removeHandler(file_handler)
    file_handler.close()
    if os.path.exists(logfile.name):
        os.remove(logfile.name)


@patch.object(SMTPAgent, 'check_banner', return_value='220 Hello')
@patch.object(ServerAgent, 'service_healthy', return_value=True)
def test_service_healthy_true(mock_parent_health, mock_banner, smtp_agent):
    """
    Test service_healthy()
    returns truthy value (banner string) when all checks pass
    """
    agent, log_path = smtp_agent
    result = agent.service_healthy()
    assert result == '220 Hello'
    assert bool(result) is True


@patch.object(SMTPAgent, 'check_banner', return_value='')
@patch.object(ServerAgent, 'service_healthy', return_value=True)
def test_service_healthy_fails_due_to_missing_banner(
    mock_parent_health,
    mock_banner,
    smtp_agent,
):
    """
    Test service_healthy()
    returns empty string (false) if banner is missing
    """
    agent, log_path = smtp_agent
    result = agent.service_healthy()
    assert result == ''
    assert bool(result) is False


@patch('agents.smtp.smtp.socket.socket')
def test_check_banner_raises_socket_error(mock_socket, smtp_agent):
    """
    Test that check_banner() returns
    empty string and logs an error
    when socket connection fails
    """
    agent, log_path = smtp_agent

    smtp_logger = agent.logger
    smtp_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)

    smtp_logger.addHandler(file_handler)
    fallback = agent.fallback_logger
    fallback.setLevel(logging.DEBUG)
    fallback.addHandler(file_handler)

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

    smtp_logger.removeHandler(file_handler)
    fallback.removeHandler(file_handler)
    file_handler.close()


@patch('agents.smtp.smtp.socket.socket')
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


@patch('subprocess.Popen')
def test_is_process_running_accepts_default_processes(mock_popen, smtp_agent):
    """
    Test that _is_process_running() returns True
    if any default SMTP process is found in the system process list.
    """
    agent, log_path = smtp_agent

    process_mock = MagicMock()
    process_mock.communicate.return_value = (
        b'master\nsendmail\npostfix\nexim\n', b'')
    mock_popen.return_value = process_mock

    for proc_name in ['postfix', 'sendmail', 'exim', 'master']:
        agent._processes = [proc_name]
        result = agent._is_process_running()
        assert result is True


@patch('subprocess.Popen')
def test_is_process_running_false_if_not_found(mock_popen, smtp_agent):
    agent, _ = smtp_agent
    agent._processes = ['postfix']

    process_mock = MagicMock()
    process_mock.communicate.return_value = (b'otherproc\n', b'')
    mock_popen.return_value = process_mock

    assert agent._is_process_running() is False
