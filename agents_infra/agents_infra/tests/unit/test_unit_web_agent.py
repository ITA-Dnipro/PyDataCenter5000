import json
import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import MagicMock, PropertyMock, patch

from ...agents.web.web import WebAgent


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
        'web_server_host': 'localhost',
        'web_server_name': 'fastapi',
    }

    with patch.object(
        WebAgent, 'logger', new_callable=PropertyMock
    ) as mock_logger:
        mock_logger.return_value = logging.getLogger('mock-logger')

        agent = WebAgent(config=config)
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


def test_check_http_health_non_200_status(
    web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 500

    with patch('urllib2.urlopen', return_value=mock_response):
        assert web_agent._check_http_health() is False, (
            'Expected _check_http_health to return False for 500 status '
            'code'
        )

    assert_msg_in_logfile('status code 500')


def test_check_http_health_missing_status_key(
    web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({})

    with patch('urllib2.urlopen', return_value=mock_response):
        assert web_agent._check_http_health() is False, (
            'Expected _check_http_health to return False for missing '
            'status key'
        )

    assert_msg_in_logfile('missing status key')


def test_check_http_health_bad_status_value(
    web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = json.dumps({'status': 'error'})

    with patch('urllib2.urlopen', return_value=mock_response):
        assert web_agent._check_http_health() is False, (
            'Expected _check_http_health to return False for error status '
            'value'
        )

    assert_msg_in_logfile('status is error')


def test_check_http_health_connection_error(
    web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    with patch('urllib2.urlopen', side_effect=Exception('Connection error')):
        assert web_agent._check_http_health() is False, (
            'Expected _check_http_health to return False on connection error'
        )

    assert_msg_in_logfile('Connection error')


def test_check_http_health_json_error(
    web_agent, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = 'INVALID JSON'

    with patch('urllib2.urlopen', return_value=mock_response):
        assert web_agent._check_http_health() is False, (
            'Expected check_http_health to return False on JSON decode error'
        )

    assert_msg_in_logfile('HTTP health check failed')


def test_web_agent_is_service_healthy_all_ok(web_agent):
    """Test is_service_healthy returns True when all checks pass"""
    with patch(
        'agents_infra.agents.base.ServerAgent.is_service_healthy',
        return_value=True
    ):
        with patch.object(WebAgent, '_check_http_health', return_value=True):
            assert web_agent.is_service_healthy() is True, (
                'Expected is_service_healthy to return True when all '
                'checks pass'
            )


def test_web_agent_is_service_healthy_parent_unhealthy(web_agent):
    """Test is_service_healthy returns False when parent check fails"""
    with patch(
        'agents_infra.agents.base.ServerAgent.is_service_healthy',
        return_value=False
    ):
        assert web_agent.is_service_healthy() is False, (
            'Expected is_service_healthy to return False when parent '
            'check fails'
        )


def test_web_agent_is_service_healthy_http_unhealthy(web_agent):
    """Test is_service_healthy returns False when HTTP check fails"""
    with patch(
        'agents_infra.agents.base.ServerAgent.is_service_healthy',
        return_value=True
    ):
        with patch.object(WebAgent, '_check_http_health', return_value=False):
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
