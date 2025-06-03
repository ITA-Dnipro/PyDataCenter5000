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

    agent = DNSAgent()
    agent.setup_logging(logfile.name)

    yield agent

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_status_to_dict_keys(dns_agent):
    """
    Verify that status_to_dict()
    returns all expected keys in the status dictionary.
    """
    dns_agent.collect_server_metadata()
    result = dns_agent.status_to_dict()
    required_keys = set(
        [
            'os',
            'hostname',
            'ip',
            'server_name',
            'uptime',
            'timestamp',
            'healthy',
        ]
    )

    assert set(result.keys()) == required_keys


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

    assert dns_agent.is_dns_running() is True


@patch('subprocess.Popen')
def test_is_dns_running_failure(mock_popen, dns_agent):
    """
    Test that is_dns_running()
    returns False when the dig command fails or returns an error.
    """
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b'', b'Some error')
    process_mock.returncode = 1
    mock_popen.return_value = process_mock

    assert dns_agent.is_dns_running() is False


@patch.object(DNSAgent, '_is_process_running', return_value=True)
@patch.object(DNSAgent, '_is_port_open', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_true(mock_dns, mock_port, mock_proc, dns_agent):
    """
    Test service_healthy()
    returns True when all checks (process, port, DNS) pass.
    """
    assert dns_agent.service_healthy() is True


@patch.object(DNSAgent, '_is_process_running', return_value=False)
@patch.object(DNSAgent, '_is_port_open', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_false(mock_dns, mock_port, mock_proc, dns_agent):
    """
    Test service_healthy()
    returns False when the process check fails, even if others pass.
    """
    assert dns_agent.service_healthy() is False


def test_is_dns_running_raises_oserror(dns_agent):
    """
    Test that is_dns_running() returns False and logs an error
    when subprocess.Popen raises an OSError.
    """
    with patch('agents.dns.dns.subprocess.Popen',
               side_effect=OSError('Mocked OSError')):
        result = dns_agent.is_dns_running()
        assert result is False
