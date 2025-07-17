# Command to run on VM: python -m pytest agents/tests/test_dns_agent.py
import os
import tempfile

import pytest
from mock import MagicMock, patch

from ...agents.dns.dns import DNSAgent


@pytest.yield_fixture
def dns_agent():
    """
    Create and configure a DNSAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    config = {
        'name': 'dns',
        'port': 53,
        'interface': 'enp0s3',
        'url': 'http://localhost',
        'api_prefix': 'api/',
        'auth_token_type': 'Bearer',
        'critical_processes': ['named'],
        'whitelist_commands': ['uptime', 'dig']
    }

    agent = DNSAgent(config=config)
    agent.setup_logging(logfile.name)

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


@patch.object(DNSAgent, 'is_dns_running', return_value=True)
@patch('agents_infra.agents.dns.dns.is_port_open', return_value=True)
@patch.object(
    DNSAgent, '_are_all_critical_processes_active', return_value=True
)
def test_is_service_healthy_true(
    mock_proc, mock_port, mock_dns, dns_agent
):
    """
    Test is_service_healthy()
    returns True when all checks (process, port, DNS) pass.
    """
    result = dns_agent.is_service_healthy()
    msg = 'Expected is_service_healthy() to return True when all checks pass'
    assert result is True, msg


@patch.object(
    DNSAgent, '_are_all_critical_processes_active', return_value=True
)
@patch.object(DNSAgent, 'is_dns_running', return_value=False)
@patch('agents_infra.agents.dns.dns.is_port_open', return_value=True)
def test_is_service_healthy_fails_due_to_dns(
    mock_proc, mock_port, mock_dns, dns_agent
):
    """
    Test is_service_healthy()
    returns False when the DNS check fails, even if others pass.
    """
    msg = (
        'Expected is_service_healthy() to return False when DNS check fails'
    )
    assert dns_agent.is_service_healthy() is False, msg


def test_is_dns_running_raises_oserror(dns_agent):
    """
    Test that is_dns_running() returns False and logs an error
    when subprocess.Popen raises an OSError.
    """
    with patch('agents_infra.agents.dns.dns.subprocess.Popen',
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
