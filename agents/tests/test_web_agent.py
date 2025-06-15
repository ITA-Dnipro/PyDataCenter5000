import json
import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import MagicMock, patch

from agents.web.web import WebAgent


@pytest.yield_fixture
def web_agent():
    """Fixture to create a WebAgent instance with required environment setup"""
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = WebAgent(log_path=logfile.name)

    handler = MemoryHandler(capacity=10000)
    agent.logger.addHandler(handler)
    agent.logger.setLevel(logging.INFO)

    yield agent, handler

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_web_agent_service_healthy_success(web_agent):
    """Test service_healthy returns True when all conditions are met"""
    agent, _ = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'ok'})

    with patch('urllib2.urlopen', return_value=mock_response):
        with patch.object(WebAgent, 'is_port_open', return_value=True):
            with patch('agents.agent.ServerAgent.service_healthy',
                       return_value=True):
                assert agent.service_healthy() is True


def test_web_agent_service_healthy_failed_status(web_agent):
    """Test service_healthy returns False on non-200 status"""
    agent, log_handler = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 500

    with patch('urllib2.urlopen', return_value=mock_response):
        result = agent.service_healthy()
        assert result is False
        assert any('status code 500' in record.getMessage()
                   for record in log_handler.buffer)


def test_web_agent_service_healthy_missing_status_key(web_agent):
    """Test service_healthy returns False when status key is missing"""
    agent, log_handler = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({})

    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent.service_healthy() is False
        assert any('missing status key' in record.getMessage()
                   for record in log_handler.buffer)


def test_web_agent_service_healthy_bad_status_value(web_agent):
    """Test service_healthy returns False with non-ok status"""
    agent, log_handler = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'error'})

    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent.service_healthy() is False
        assert any('status is error' in record.getMessage()
                   for record in log_handler.buffer)


def test_web_agent_service_healthy_port_closed(web_agent):
    """Test service_healthy returns False when port is closed"""
    agent, _ = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'ok'})

    with patch('urllib2.urlopen', return_value=mock_response):
        with patch.object(WebAgent, 'is_port_open', return_value=False):
            assert agent.service_healthy() is False


def test_web_agent_service_healthy_parent_unhealthy(web_agent):
    """Test service_healthy returns False when parent check fails"""
    agent, _ = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'ok'})

    with patch('urllib2.urlopen', return_value=mock_response):
        with patch('agents.agent.ServerAgent.service_healthy',
                   return_value=False):
            assert agent.service_healthy() is False


def test_web_agent_service_healthy_connection_error(web_agent):
    """Test service_healthy handles connection errors"""
    agent, log_handler = web_agent

    with patch('urllib2.urlopen', side_effect=Exception('Connection error')):
        assert agent.service_healthy() is False
        assert any('Connection error' in record.getMessage()
                   for record in log_handler.buffer)


def test_web_agent_service_healthy_json_error(web_agent):
    """Test service_healthy handles invalid JSON responses"""
    agent, log_handler = web_agent

    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = 'INVALID JSON'

    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent.service_healthy() is False
        assert any('Health check failed' in record.getMessage()
                   for record in log_handler.buffer)


def test_web_agent_build_url(web_agent):
    """Test URL construction"""
    agent, _ = web_agent
    agent.server_host = 'localhost'
    agent.port = 8000
    assert agent._build_url('health') == 'http://localhost:8000/health'
    assert agent._build_url('metrics') == 'http://localhost:8000/metrics'


def test_web_agent_get_env_or_param(web_agent):
    """Test environment variable handling"""
    agent, _ = web_agent

    # Store original value if it exists
    original_value = os.environ.get('TEST_VAR')

    try:
        os.environ['TEST_VAR'] = 'env_value'
        assert agent._get_env_or_param(None, 'TEST_VAR') == 'env_value'

        assert agent._get_env_or_param('mock_val', 'TEST_VAR') == 'mock_val'

        del os.environ['TEST_VAR']
        with pytest.raises(ValueError):
            agent._get_env_or_param(None, 'MISSING_VAR')

    finally:
        # Clean up
        if original_value is not None:
            os.environ['TEST_VAR'] = original_value
        elif 'TEST_VAR' in os.environ:
            del os.environ['TEST_VAR']
