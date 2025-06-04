import os
import tempfile

import pytest
from mock import MagicMock, patch

from agents.smtp.smtp import SMTPAgent


@pytest.yield_fixture
def smtp_agent():
    """
    Create and configure a SMTPAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    os.environ['PORT'] = '25'
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = SMTPAgent()
    agent.setup_logging(logfile.name)

    yield agent

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_status_to_dict_keys(smtp_agent):
    """
    Verify that status_to_dict() returns all expected keys
    in the status dictionary, including banner
    """
    with patch.object(smtp_agent, 'collect_server_metadata') as mock_collect, \
            patch.object(
                smtp_agent,
                'check_banner',
                return_value='220 smtp.example.com ESMTP'
                ), \
            patch.object(smtp_agent, 'service_healthy', return_value=True):

        smtp_agent.os_type = 'linux'
        smtp_agent.hostname = 'test-host'
        smtp_agent.ip = '127.0.0.1'
        smtp_agent.server_name = 'smtp'
        smtp_agent.uptime = 12345
        smtp_agent.timestamp = '2025-06-03 20:00:00'
        smtp_agent.healthy = True

        result = smtp_agent.status_to_dict()

        required_keys = {
            'os',
            'hostname',
            'ip',
            'server_name',
            'uptime',
            'timestamp',
            'healthy',
            'banner'
        }

        assert set(result.keys()) == required_keys
        assert result['banner'] == '220 smtp.example.com ESMTP'
        mock_collect.assert_called_once()


def test_status_to_dict_with_missing_fields(smtp_agent):
    """
    Ensure status_to_dict() handles missing or None fields gracefully.
    """
    with patch.object(smtp_agent, 'collect_server_metadata'), \
            patch.object(smtp_agent, 'check_banner', return_value=''), \
            patch.object(smtp_agent, 'service_healthy', return_value=False):

        smtp_agent.os_type = None
        smtp_agent.hostname = None
        smtp_agent.ip = None
        smtp_agent.server_name = 'smtp'
        smtp_agent.uptime = -1
        smtp_agent.timestamp = None
        smtp_agent.healthy = False

        result = smtp_agent.status_to_dict()

        assert result['os'] is None
        assert result['hostname'] is None
        assert result['ip'] is None
        assert result['uptime'] == -1
        assert result['healthy'] is False
        assert result['banner'] is None


@patch.object(SMTPAgent, '_is_process_running', return_value=True)
@patch.object(SMTPAgent, '_is_port_open', return_value=True)
@patch.object(SMTPAgent, 'check_banner',
              return_value='220 smtp.example.com ESMTP')
def test_service_healthy_true(mock_proc, mock_port, mock_banner, smtp_agent):
    """
    Test service_healthy()
    returns True when all checks (process, port)
    pass and banner is present
    """
    assert smtp_agent.service_healthy() is True


@patch.object(SMTPAgent, '_is_process_running', return_value=True)
@patch.object(SMTPAgent, '_is_port_open', return_value=True)
@patch.object(SMTPAgent, 'check_banner', return_value='')
def test_service_healthy_fails_due_to_missing_banner(
    mock_banner,
    mock_port,
    mock_proc,
    smtp_agent,
):
    """
    Test service_healthy()
    returns False if banner is missing
    even if others pass.
    """
    assert smtp_agent.service_healthy() is False


@patch('agents.smtp.smtp.maybe_log_message')
def test_check_banner_raises_socket_error(mock_log, smtp_agent):
    """
    Test that check_banner() returns
    empty string and logs an error
    when socket connection fails
    """
    with patch('socket.socket.connect', side_effect=Exception('Mocked error')):
        result = smtp_agent.check_banner()
        assert result == ''
        assert mock_log.called


@patch('socket.socket.connect', return_value=None)
@patch('socket.socket.recv', return_value=b'220 smtp.example.com ESMTP')
def test_check_banner_success(mock_connect, mock_recv, smtp_agent):
    """
    Test that check_banner() successfully reads
    and returns banner string
    """
    smtp_agent.ip = '127.0.0.1'
    result = smtp_agent.check_banner()
    assert result == b'220 smtp.example.com ESMTP'.strip()


@patch('agents.smtp.smtp.socket.socket')
def test_is_port_open_success(mock_socket, smtp_agent):
    """
    Test that _is_port_open() returns
    True when the connection succeeds.
    """
    smtp_agent.ip = '127.0.0.1'
    mock_sock = MagicMock()
    mock_socket.return_value = mock_sock

    result = smtp_agent._is_port_open()
    assert result is True
    mock_sock.connect.assert_called_once()


@patch('agents.smtp.smtp.socket.socket')
def test_is_port_open_failure(mock_socket, smtp_agent):
    """
    Test that _is_port_open() returns False
    when the connection fails.
    """
    smtp_agent.ip = '127.0.0.1'
    mock_sock = MagicMock()
    mock_sock.connect.side_effect = Exception('Connection failed')
    mock_socket.return_value = mock_sock

    result = smtp_agent._is_port_open()
    assert result is False


@pytest.mark.parametrize('proc_name',
                         ['postfix', 'sendmail', 'exim', 'master'])
@patch('subprocess.Popen')
def test_is_process_running_accepts_default_processes(
        proc_name, mock_popen, smtp_agent):
    """
    Test that _is_process_running() returns True
    if any default SMTP process is found in the system process list.
    """
    process_mock = MagicMock()
    process_mock.communicate.return_value = (
        'master\nsendmail\npostfix\nexim\n', '')
    mock_popen.return_value = process_mock

    smtp_agent._processes = [proc_name]
    result = smtp_agent._is_process_running()
    assert result is True


@patch('subprocess.Popen', side_effect=OSError('ps failed'))
@patch('agents.smtp.smtp.maybe_log_message')
def test_is_process_running_exception(mock_log, mock_popen, smtp_agent):
    """
    Test that _is_process_running() returns False
    and logs an error when subprocess execution fails.
    """
    result = smtp_agent._is_process_running()
    assert result is False
    assert mock_log.called


@patch.object(SMTPAgent, 'status_to_dict', return_value={'ok': True})
@patch('agents.smtp.smtp.json.dumps', return_value='{"ok": true}')
def test_status_to_json_serialization(mock_json, mock_dict, smtp_agent):
    """
    Test that status_to_json() returns a valid
    JSON-formatted string
    """
    result = smtp_agent.status_to_json(log=False)
    assert result == '{"ok": true}'


@patch('agents.smtp.smtp.urllib2.urlopen')
@patch('agents.smtp.smtp.json.dumps', return_value='{"ok": true}')
@patch.object(SMTPAgent, 'status_to_dict', return_value={'ok': True})
def test_status_to_controller_success(
        mock_dict,
        mock_json,
        mock_urlopen,
        smtp_agent):
    """
    Test that status_to_controller() sends
    data to the controller successfully.
    """
    smtp_agent.controller_url = 'http://localhost:8000'
    smtp_agent.status_to_controller()
    assert mock_urlopen.called


@patch('agents.smtp.smtp.urllib2.urlopen',
       side_effect=Exception('Connection failed'))
@patch('agents.smtp.smtp.maybe_log_message')
@patch('agents.smtp.smtp.json.dumps', return_value='{"ok": true}')
@patch.object(SMTPAgent, 'status_to_dict', return_value={'ok': True})
def test_status_to_controller_failure(
        mock_dict,
        mock_json,
        mock_log,
        mock_urlopen,
        smtp_agent):
    """
    Test that status_to_controller() logs an error
    when sending data fails.
    """
    smtp_agent.controller_url = 'http://localhost:8000'
    smtp_agent.status_to_controller()
    assert mock_log.called
