import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import patch

from agents.web.web import WebAgent


@pytest.yield_fixture
def web_agent():
    """Fixture to create a WebAgent instance with required environment setup"""
    os.environ['PORT'] = '8000'

    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = WebAgent(log_path=logfile.name)

    handler = MemoryHandler(capacity=10000)
    agent.logger.addHandler(handler)
    agent.logger.setLevel(logging.INFO)

    yield agent, handler

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_to_dict_format(web_agent):
    """Test that to_dict returns a dictionary with correct key-value types"""
    web_agent, _ = web_agent

    web_agent.collect_server_metadata()  # Initialize metadata
    result = web_agent.status_to_dict()

    # Check all required keys are present
    required_keys = set(
        [
            'os', 'hostname', 'ip', 'server_name', 'uptime', 'timestamp',
            'healthy'
        ]
    )
    assert set(result.keys()) == required_keys

    # Check value types
    assert isinstance(result['os'], str)
    assert isinstance(result['hostname'], str)
    assert isinstance(result['ip'], (str, type(None)))
    assert result['server_name'] == 'web'
    assert isinstance(result['uptime'], (int, float))
    assert isinstance(result['timestamp'], str)
    assert isinstance(result['healthy'], bool)


def test_to_dict_timestamp_format(web_agent):
    """Test that timestamp in to_dict follows the correct format"""
    web_agent, _ = web_agent

    web_agent.collect_server_metadata()  # Initialize metadata
    result = web_agent.status_to_dict()
    timestamp = result['timestamp']

    # Check timestamp format (YYYY-MM-DD HH:MM:SS)
    import re
    assert re.match(
        r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp
    ) is not None


@patch('agents.web.web.WebAgent.service_healthy')
def test_to_dict_healthy_status(mock_healthy, web_agent):
    """Test that healthy status is correctly reflected in to_dict"""
    web_agent, _ = web_agent

    # Test when service is healthy
    mock_healthy.return_value = True
    result = web_agent.status_to_dict()
    assert result['healthy'] is True

    # Test when service is unhealthy
    mock_healthy.return_value = False
    result = web_agent.status_to_dict()
    assert result['healthy'] is False


def test_to_txt(web_agent):
    """Test that to_txt logs each key-value pair"""
    web_agent, handler = web_agent

    web_agent.status_to_txt()

    # Get all logged messages
    logged_messages = [record.getMessage() for record in handler.buffer]

    # Check that each key-value pair from to_dict is logged
    dict_data = web_agent.status_to_dict()
    for key, value in dict_data.items():
        expected_message = '%s: %s' % (key, value)
        assert expected_message in logged_messages
