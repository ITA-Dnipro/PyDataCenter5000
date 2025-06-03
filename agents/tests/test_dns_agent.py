# Command to run on VM: python -m pytest agents/tests/test_dns_agent.py
import os
import tempfile

import pytest
from mock import MagicMock, patch

from agents.dns.dns import DNSAgent


@pytest.yield_fixture
def dns_agent():
    os.environ['PORT'] = '53'
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = DNSAgent()
    agent.setup_logging(logfile.name)

    yield agent

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_status_to_dict_keys(dns_agent):
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
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b'8.8.8.8\n', b'')
    process_mock.returncode = 0
    mock_popen.return_value = process_mock

    assert dns_agent.is_dns_running() is True


@patch('subprocess.Popen')
def test_is_dns_running_failure(mock_popen, dns_agent):
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b'', b'Some error')
    process_mock.returncode = 1
    mock_popen.return_value = process_mock

    assert dns_agent.is_dns_running() is False


@patch.object(DNSAgent, '_is_process_running', return_value=True)
@patch.object(DNSAgent, '_is_port_open', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_true(mock_dns, mock_port, mock_proc, dns_agent):
    assert dns_agent.service_healthy() is True


@patch.object(DNSAgent, '_is_process_running', return_value=False)
@patch.object(DNSAgent, '_is_port_open', return_value=True)
@patch.object(DNSAgent, 'is_dns_running', return_value=True)
def test_service_healthy_false(mock_dns, mock_port, mock_proc, dns_agent):
    assert dns_agent.service_healthy() is False
