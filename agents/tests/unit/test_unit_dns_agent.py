# Command to run on VM: python -m pytest agents/tests/test_dns_agent.py
import os
import tempfile

import pytest
from mock import MagicMock, patch

from agents import DNSAgent


@pytest.yield_fixture
def dns_agent():
    """
    Create and configure a DNSAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = DNSAgent(log_path=logfile.name)

    yield agent

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


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


@patch.object(DNSAgent, 'is_port_open', return_value=True)
@patch.object(DNSAgent, '_is_process_running', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_true(mock_dns, mock_port, mock_proc, dns_agent):
    """
    Test service_healthy()
    returns True when all checks (process, port, DNS) pass.
    """
    msg = 'Expected service_healthy() to return True when all checks pass'
    assert dns_agent.service_healthy() is True, msg


@patch.object(DNSAgent, 'is_port_open', return_value=True)
@patch.object(DNSAgent, '_is_process_running', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=False)
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
