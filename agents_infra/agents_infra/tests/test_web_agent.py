import json
import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import MagicMock, patch

from ..agents.web.web import WebAgent


@pytest.yield_fixture
def web_agent():
    """Fixture to create a WebAgent instance with required environment setup"""
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = WebAgent(port=8000,
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
        with patch('agents_infra.agents.base.ServerAgent.is_service_healthy',
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
        with patch('agents_infra.agents.base.ServerAgent.is_service_healthy',
                   return_value=False):
            assert agent.is_service_healthy() is False, (
                'Expected is_service_healthy to return False when parent '
                'check fails'
            )


def test_web_agent_is_service_healthy_http_unhealthy(web_agent):
    """Test is_service_healthy returns False when HTTP check fails"""
    agent, _ = web_agent
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents_infra.agents.base.ServerAgent.is_service_healthy',
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


def test_maybe_restart_service_when_all_services_active(web_agent):
    """
    Should return True and log healthy status if all services are running.
    """
    agent, _ = web_agent
    agent._check_http_health = MagicMock(return_value=True)
    agent.is_ssh_service_active = MagicMock(return_value=True)

    with patch('agents_infra.agents.web.web.maybe_log_message') as mock_log:
        with patch(
                  'agents_infra.agents.web.web.restart_service'
                  ) as mock_restart:

            result = agent.maybe_restart_service()

            assert result is True
            assert not mock_restart.called, (
                'restart_service should not be called '
                'when services are running.'
            )

            mock_log.assert_called_with(
                'All services are healthy and running',
                agent.logger,
                fallback_logger=agent.fallback_logger,
                level=logging.INFO
            )


def test_maybe_restart_service_when_web_inactive(web_agent):
    """
    Should restart only 'fastapi' service if Web is not running.
    """
    agent, _ = web_agent
    agent._check_http_health = MagicMock(return_value=False)
    agent.is_ssh_service_active = MagicMock(return_value=True)

    with patch('agents_infra.agents.web.web.maybe_log_message') as mock_log:
        with patch(
                  'agents_infra.agents.web.web.restart_service'
                  ) as mock_restart:

            result = agent.maybe_restart_service()

            assert result is False
            mock_restart.assert_called_once_with(
                agent.logger, agent.fallback_logger, 'fastapi'
            )

            mock_log.assert_any_call(
                'Finished attempts to restart services',
                agent.logger,
                fallback_logger=agent.fallback_logger,
                level=logging.INFO
            )


def test_maybe_restart_service_when_ssh_inactive(web_agent):
    """
    Should restart only 'ssh' service if SSH is not active.
    """
    agent, _ = web_agent
    agent._check_http_health = MagicMock(return_value=True)
    agent.is_ssh_service_active = MagicMock(return_value=False)

    with patch('agents_infra.agents.web.web.maybe_log_message') as mock_log:
        with patch(
                  'agents_infra.agents.web.web.restart_service'
                  ) as mock_restart:

            result = agent.maybe_restart_service()

            assert result is False
            mock_restart.assert_called_once_with(
                agent.logger, agent.fallback_logger, 'ssh'
            )

            mock_log.assert_any_call(
                'Finished attempts to restart services',
                agent.logger,
                fallback_logger=agent.fallback_logger,
                level=logging.INFO
            )


def test_maybe_restart_service_when_both_services_inactive(web_agent):
    """
    Should restart both 'fastapi' and 'ssh' services.
    """
    agent, _ = web_agent
    agent._check_http_health = MagicMock(return_value=False)
    agent.is_ssh_service_active = MagicMock(return_value=False)

    with patch('agents_infra.agents.web.web.maybe_log_message') as mock_log:
        with patch(
                  'agents_infra.agents.web.web.restart_service'
                  ) as mock_restart:

            result = agent.maybe_restart_service()

            assert result is False
            assert mock_restart.call_count == 2
            mock_restart.assert_any_call(
                agent.logger, agent.fallback_logger, 'fastapi'
            )
            mock_restart.assert_any_call(
                agent.logger, agent.fallback_logger, 'ssh'
            )

            mock_log.assert_any_call(
                'Finished attempts to restart services',
                agent.logger,
                fallback_logger=agent.fallback_logger,
                level=logging.INFO
            )


def test_is_service_healthy_logs_exception(web_agent):
    """
    Should log an error and return False if an exception is raised in
    is_service_healthy.
    """
    agent, _ = web_agent
    with patch('agents_infra.agents.web.web.maybe_log_message') as mock_log:
        # Force _check_http_health to raise an exception
        agent._check_http_health = MagicMock(
            side_effect=Exception('test error')
        )
        result = agent.is_service_healthy()
        assert result is False
        mock_log.assert_called_once()
        assert (
            'Health check failed with error: test error'
            in mock_log.call_args[0][0]
        ), (
            'Expected error message to be logged when exception is raised '
            'in is_service_healthy'
        )
