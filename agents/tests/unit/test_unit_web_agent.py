import json
import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import MagicMock, patch

from agents import WebAgent


@pytest.yield_fixture
def web_agent():
    """
    Create and configure a WebAgent instance with logging for use in tests.
    Cleans up the temporary log file after the test completes.
    """
    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    config = {
        'name': 'web',
        'port': 8000,
        'interface': None,
        'url': 'http://localhost',
        'api_prefix': 'api/v1/',
        'auth_token_type': None,
        'critical_processes': [],
        'whitelist_commands': [],
    }

    agent = WebAgent(
        config=config,
        web_server_host='localhost',
        web_server_name='fastapi',
    )
    agent.setup_logging(logfile.name)

    yield agent

    if os.path.exists(logfile.name):
        os.remove(logfile.name)


def test_check_http_health_success(web_agent):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'ok'})

    with patch('urllib2.urlopen', return_value=mock_response):
        assert web_agent._check_http_health() is True, (
            'Expected _check_http_health to return True for 200 OK '
            'response'
        )


# def test_check_http_health_non_200_status(
#     web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
# ):
#     mock_response = MagicMock()
#     mock_response.getcode.return_value = 500

#     with patch('urllib2.urlopen', return_value=mock_response):
#         assert web_agent._check_http_health() is False, (
#             'Expected _check_http_health to return False for 500 status '
#             'code'
#         )

#     assert_msg_in_logfile('status code 500')

def test_check_http_health_non_200_status(
    web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 500

    with patch('urllib2.urlopen', return_value=mock_response):
        assert web_agent._check_http_health() is False

    assert_msg_in_logfile('status code 500')


# def test_check_http_health_missing_status_key(
#     web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
# ):
#     mock_response = MagicMock()
#     mock_response.getcode.return_value = 200
#     mock_response.read.return_value = json.dumps({})

#     with patch('urllib2.urlopen', return_value=mock_response):
#         assert web_agent._check_http_health() is False, (
#             'Expected _check_http_health to return False for missing '
#             'status key'
#         )

#     assert_msg_in_logfile('missing status key')


# def test_check_http_health_bad_status_value(
#     web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
# ):
#     mock_response = MagicMock()
#     mock_response.getcode.return_value = 200
#     mock_response.read.return_value = json.dumps({'status': 'error'})

#     with patch('urllib2.urlopen', return_value=mock_response):
#         assert web_agent._check_http_health() is False, (
#             'Expected _check_http_health to return False for error status '
#             'value'
#         )

#     assert_msg_in_logfile('status is error')


# def test_check_http_health_connection_error(
#     web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
# ):
#     with patch('urllib2.urlopen', side_effect=Exception('Connection error')):
#         assert web_agent._check_http_health() is False, (
#             'Expected _check_http_health to return False on connection error'
#         )

#     assert_msg_in_logfile('Connection error')


# def test_check_http_health_json_error(
#     web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
# ):
#     mock_response = MagicMock()
#     mock_response.getcode.return_value = 200
#     mock_response.read.return_value = 'INVALID JSON'

#     with patch('urllib2.urlopen', return_value=mock_response):
#         assert web_agent._check_http_health() is False, (
#             'Expected check_http_health to return False on JSON decode error'
#         )

#     assert_msg_in_logfile('HTTP health check failed')


def test_web_agent_is_service_healthy_all_ok(web_agent):
    """Test is_service_healthy returns True when all checks pass"""
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents.agent.ServerAgent.is_service_healthy',
                   return_value=True):
            with patch.object(WebAgent, '_check_http_health',
                              return_value=True):
                assert web_agent.is_service_healthy() is True, (
                    'Expected is_service_healthy to return True when all '
                    'checks pass'
                )


def test_web_agent_is_service_healthy_port_closed(web_agent):
    """Test is_service_healthy returns False when port is closed"""
    with patch.object(WebAgent, 'is_port_open', return_value=False):
        assert web_agent.is_service_healthy() is False, (
            'Expected is_service_healthy to return False when port is closed'
        )


def test_web_agent_is_service_healthy_parent_unhealthy(web_agent):
    """Test is_service_healthy returns False when parent check fails"""
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents.agent.ServerAgent.is_service_healthy',
                   return_value=False):
            assert web_agent.is_service_healthy() is False, (
                'Expected is_service_healthy to return False when parent '
                'check fails'
            )


def test_web_agent_is_service_healthy_http_unhealthy(web_agent):
    """Test is_service_healthy returns False when HTTP check fails"""
    with patch.object(WebAgent, 'is_port_open', return_value=True):
        with patch('agents.agent.ServerAgent.is_service_healthy',
                   return_value=True):
            with patch.object(WebAgent, '_check_http_health',
                              return_value=False):
                assert web_agent.is_service_healthy() is False, (
                    'Expected is_service_healthy to return False when HTTP '
                    'check fails'
                )


def test_web_agent_build_url(web_agent):
    """Test URL construction"""
    web_agent.web_server_host = 'localhost'
    web_agent.port = 8000
    assert web_agent._build_url('health') == 'http://localhost:8000/health', (
        'Expected health URL to be http://localhost:8000/health'
    )
    assert web_agent._build_url(
        'metrics'
    ) == 'http://localhost:8000/metrics', (
        'Expected metrics URL to be http://localhost:8000/metrics'
    )


def test_maybe_restart_service_when_all_services_active(web_agent):
    """
    Should return True and log healthy status if all services are running.
    """
    web_agent._check_http_health = MagicMock(return_value=True)
    web_agent.is_ssh_service_active = MagicMock(return_value=True)

    with patch('agents.web.web.maybe_log_message') as mock_log:
        with patch('agents.web.web.restart_service') as mock_restart:

            result = web_agent.maybe_restart_service()

            assert result is True
            assert not mock_restart.called, (
                'restart_service should not be called '
                'when services are running.'
            )

            mock_log.assert_called_with(
                'All services are healthy and running',
                logger=web_agent.logger,
                level=logging.INFO
            )


def test_maybe_restart_service_when_web_inactive(web_agent):
    """
    Should restart only 'fastapi' service if Web is not running.
    """
    web_agent._check_http_health = MagicMock(return_value=False)
    web_agent.is_ssh_service_active = MagicMock(return_value=True)

    with patch('agents.web.web.maybe_log_message') as mock_log:
        with patch('agents.web.web.restart_service') as mock_restart:

            result = web_agent.maybe_restart_service()

            assert result is False
            mock_restart.assert_called_once_with(
                'fastapi', logger=web_agent.logger
            )

            mock_log.assert_any_call(
                'Finished attempts to restart services',
                logger=web_agent.logger,
                level=logging.INFO
            )


def test_maybe_restart_service_when_ssh_inactive(web_agent):
    """
    Should restart only 'ssh' service if SSH is not active.
    """
    web_agent._check_http_health = MagicMock(return_value=True)
    web_agent.is_ssh_service_active = MagicMock(return_value=False)

    with patch('agents.web.web.maybe_log_message') as mock_log:
        with patch('agents.web.web.restart_service') as mock_restart:

            result = web_agent.maybe_restart_service()

            assert result is False
            mock_restart.assert_called_once_with(
                'ssh', logger=web_agent.logger
            )

            mock_log.assert_any_call(
                'Finished attempts to restart services',
                logger=web_agent.logger,
                level=logging.INFO
            )


def test_maybe_restart_service_when_both_services_inactive(web_agent):
    """
    Should restart both 'fastapi' and 'ssh' services.
    """
    web_agent._check_http_health = MagicMock(return_value=False)
    web_agent.is_ssh_service_active = MagicMock(return_value=False)

    with patch('agents.web.web.maybe_log_message') as mock_log:
        with patch('agents.web.web.restart_service') as mock_restart:

            result = web_agent.maybe_restart_service()

            assert result is False
            assert mock_restart.call_count == 2
            mock_restart.assert_any_call('fastapi', logger=web_agent.logger)
            mock_restart.assert_any_call('ssh', logger=web_agent.logger)

            mock_log.assert_any_call(
                'Finished attempts to restart services',
                logger=web_agent.logger,
                level=logging.INFO
            )


def test_is_service_healthy_logs_exception(web_agent):
    """
    Should log an error and return False if an exception is raised in
    is_service_healthy.
    """
    with patch('agents.web.web.maybe_log_message') as mock_log:
        # Force _check_http_health to raise an exception
        web_agent._check_http_health = MagicMock(
            side_effect=Exception('test error')
        )
        result = web_agent.is_service_healthy()
        assert result is False
        mock_log.assert_called_once()
        assert (
            'Health check failed with error: test error'
            in mock_log.call_args[0][0]
        ), (
            'Expected error message to be logged when exception is raised '
            'in is_service_healthy'
        )
