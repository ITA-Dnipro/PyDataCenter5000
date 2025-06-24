import json
import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import MagicMock, patch

from agents.web.web import WebAgent


class DummyWebAgent(WebAgent):

    def maybe_restart_service(self, *args, **kwargs):
        return False


@pytest.yield_fixture
def web_agent():
    """Fixture to create a WebAgent instance with required environment setup"""
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = DummyWebAgent(port=8000,
                          web_server_host='localhost',
                          web_server_name='fastapi',)
    agent.setup_logging(logfile.name)

    handler = MemoryHandler(capacity=10000)
    agent.logger.addHandler(handler)
    agent.logger.setLevel(logging.INFO)

    yield agent, handler

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_check_http_health_success(web_agent):
    agent, _ = web_agent
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'ok'})
    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent._check_http_health() is True, (
            'Expected _check_http_health to return True for 200 OK '
            'response'
        )


def test_check_http_health_non_200_status(web_agent):
    agent, log_handler = web_agent
    mock_response = MagicMock()
    mock_response.getcode.return_value = 500
    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent._check_http_health() is False, (
            'Expected _check_http_health to return False for 500 status '
            'code'
        )
        assert any('status code 500' in record.getMessage()
                   for record in log_handler.buffer), (
            'Expected log message for status code 500'
        )


def test_check_http_health_missing_status_key(web_agent):
    agent, log_handler = web_agent
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({})
    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent._check_http_health() is False, (
            'Expected _check_http_health to return False for missing '
            'status key'
        )
        assert any('missing status key' in record.getMessage()
                   for record in log_handler.buffer), (
            'Expected log message for missing status key'
        )


def test_check_http_health_bad_status_value(web_agent):
    agent, log_handler = web_agent
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'error'})
    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent._check_http_health() is False, (
            'Expected _check_http_health to return False for error status '
            'value'
        )
        assert any('status is error' in record.getMessage()
                   for record in log_handler.buffer), (
            'Expected log message for error status value'
        )


def test_check_http_health_connection_error(web_agent):
    agent, log_handler = web_agent
    with patch('urllib2.urlopen', side_effect=Exception('Connection error')):
        assert agent._check_http_health() is False, (
            'Expected _check_http_health to return False on connection error'
        )
        assert any('Connection error' in record.getMessage()
                   for record in log_handler.buffer), (
            'Expected log message for connection error'
        )


def test_check_http_health_json_error(web_agent):
    agent, log_handler = web_agent
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = 'INVALID JSON'
    with patch('urllib2.urlopen', return_value=mock_response):
        assert agent._check_http_health() is False, (
            'Expected _check_http_health to return False on JSON decode error'
        )
        assert any('HTTP health check failed' in record.getMessage()
                   for record in log_handler.buffer), (
            'Expected log message for HTTP health check failure'
        )


def test_web_agent_is_service_healthy_all_ok(web_agent):
    """Test is_service_healthy returns True when all checks pass"""
    agent, _ = web_agent
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents.agent.ServerAgent.is_service_healthy',
                   return_value=True):
            with patch.object(WebAgent, '_check_http_health',
                              return_value=True):
                assert agent.is_service_healthy() is True, (
                    'Expected is_service_healthy to return True when all '
                    'checks pass'
                )


def test_web_agent_is_service_healthy_port_closed(web_agent):
    """Test is_service_healthy returns False when port is closed"""
    agent, _ = web_agent
    with patch.object(WebAgent, 'is_port_open', return_value=False):
        assert agent.is_service_healthy() is False, (
            'Expected is_service_healthy to return False when port is closed'
        )


def test_web_agent_is_service_healthy_parent_unhealthy(web_agent):
    """Test is_service_healthy returns False when parent check fails"""
    agent, _ = web_agent
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents.agent.ServerAgent.is_service_healthy',
                   return_value=False):
            assert agent.is_service_healthy() is False, (
                'Expected is_service_healthy to return False when parent '
                'check fails'
            )


def test_web_agent_is_service_healthy_http_unhealthy(web_agent):
    """Test is_service_healthy returns False when HTTP check fails"""
    agent, _ = web_agent
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents.agent.ServerAgent.is_service_healthy',
                   return_value=True):
            with patch.object(WebAgent, '_check_http_health',
                              return_value=False):
                assert agent.is_service_healthy() is False, (
                    'Expected is_service_healthy to return False when HTTP '
                    'check fails'
                )


def test_web_agent_build_url(web_agent):
    """Test URL construction"""
    agent, _ = web_agent
    agent.web_server_host = 'localhost'
    agent.port = 8000
    assert agent._build_url('health') == 'http://localhost:8000/health', (
        'Expected health URL to be http://localhost:8000/health'
    )
    assert agent._build_url('metrics') == 'http://localhost:8000/metrics', (
        'Expected metrics URL to be http://localhost:8000/metrics'
    )
