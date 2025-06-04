# Command to run on VM: python -m pytest agents/tests/test_dns_agent.py
import os
import tempfile

import pytest
from mock import MagicMock, patch

from agents.dns.dns import DNSAgent


@pytest.yield_fixture
def dns_agent():
    """
    Create and configure a DNSAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    os.environ['PORT'] = '53'
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = DNSAgent(query_domain='google.com')
    agent.setup_logging(logfile.name)

    yield agent

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_status_to_dict_keys(dns_agent):
    """
    Verify that status_to_dict() returns all expected keys
    in the status dictionary.
    Uses mock to isolate from metadata collection implementation.
    """
    with patch.object(dns_agent, 'collect_server_metadata') as mock_collect:
        dns_agent.os_type = 'linux'
        dns_agent.hostname = 'test-host'
        dns_agent.ip = '127.0.0.1'
        dns_agent.server_name = 'dns'
        dns_agent.uptime = 12345
        dns_agent.timestamp = '2025-06-03 20:00:00'
        dns_agent.healthy = True

        result = dns_agent.status_to_dict()

        required_keys = set([
            'os',
            'hostname',
            'ip',
            'server_name',
            'uptime',
            'timestamp',
            'healthy',
            ])
        msg_mock = 'Expected collect_server_metadata() to be called only once'
        mock_collect.assert_called_once(), msg_mock

        msg_keys = (
            'Expected status_to_dict() keys to match required keys: {}'
            .format(required_keys)
        )
        assert set(result.keys()) == required_keys, msg_keys


def test_status_to_dict_with_missing_fields(dns_agent):
    """
    Ensure status_to_dict() handles missing or None fields gracefully.
    """
    with patch.object(dns_agent, 'collect_server_metadata'):
        dns_agent.os_type = None
        dns_agent.hostname = None
        dns_agent.ip = None
        dns_agent.server_name = 'dns'
        dns_agent.uptime = -1
        dns_agent.timestamp = None
        dns_agent.healthy = False

        result = dns_agent.status_to_dict()

        assert result['os'] is None, "Expected 'os' to be None when missing"
        assert result['hostname'] is None, "Expected 'hostname' to be None"
        assert result['ip'] is None, "Expected 'ip' to be None when missing"
        assert result['uptime'] == -1, "Expected 'uptime' to be-1 when missing"
        assert result['healthy'] is False, "Expected 'healthy' to be False"


@patch('subprocess.Popen')
def test_is_dns_running_success(mock_popen, dns_agent):
    """
    Test that is_dns_running()
    returns True when the dig command succeeds with output.
    """
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b'8.8.8.8\n', b'')
    process_mock.returncode = 0
    mock_popen.return_value = process_mock

    result = dns_agent.is_dns_running()
    msg = 'Expected is_dns_running() to return True for valid dig output'
    assert result, msg


@patch('subprocess.Popen')
def test_is_dns_running_failures(mock_popen, dns_agent):
    """
    Test that is_dns_running() returns False in various failure scenarios:
    - returncode is non-zero
    - output is empty
    - output is not a valid IP address
    """
    test_cases = [
        (1, b'8.8.8.8', b'', 'Non-zero return code should return False'),
        (0, b'', b'', 'Empty output should return False'),
        (0, b'invalid-response', b'', 'Invalid IP output should return False'),
    ]

    for returncode, stdout, stderr, msg in test_cases:
        process_mock = MagicMock()
        process_mock.communicate.return_value = (stdout, stderr)
        process_mock.returncode = returncode
        mock_popen.return_value = process_mock

        assert dns_agent.is_dns_running() is False, msg


@patch.object(DNSAgent, '_is_process_running', return_value=True)
@patch.object(DNSAgent, '_is_port_open', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_true(mock_dns, mock_port, mock_proc, dns_agent):
    """
    Test service_healthy()
    returns True when all checks (process, port, DNS) pass.
    """
    msg = 'Expected service_healthy() to return True when all checks pass'
    assert dns_agent.service_healthy() is True, msg


@patch.object(DNSAgent, '_is_process_running', return_value=False)
@patch.object(DNSAgent, '_is_port_open', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_fails_due_to_process(
    mock_dns,
    mock_port,
    mock_proc,
    dns_agent,
):
    """
    Test service_healthy()
    returns False when the process check fails, even if others pass.
    """
    msg = (
        'Expected service_healthy() to return False when process check fails'
    )
    assert dns_agent.service_healthy() is False, msg


def test_is_dns_running_raises_oserror(dns_agent):
    """
    Test that is_dns_running() returns False and logs an error
    when subprocess.Popen raises an OSError.
    """
    with patch('agents.dns.dns.subprocess.Popen',
               side_effect=OSError('Mocked OSError')):
        result = dns_agent.is_dns_running()

    msg_result = (
        'Expected is_dns_running() to return False when Popen raises OSError'
    )
    assert result is False, msg_result

    # Check if message about errors exist in temp logfile
    with open(dns_agent.logger.handlers[0].baseFilename, 'r') as f:
        log_content = f.read()

    msg_log_dns_failed = "Log should include 'DNS check failed' after OSError"
    msg_log_oserror = "Log should include 'Mocked OSError' after OSError"

    assert 'DNS check failed' in log_content, msg_log_dns_failed
    assert 'Mocked OSError' in log_content, msg_log_oserror
