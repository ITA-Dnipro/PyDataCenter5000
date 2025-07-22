import json
import logging
import socket

import mock
import pytest
import urllib2
from agents_infra.utils.network import (check_http_health,
                                        find_first_healthy_url,
                                        is_tcp_reachable, ping_url)


def test_find_healthy_controller_returns_first_healthy(monkeypatch):
    urls = [
        'http://mock-controller1',
        'http://mock-controller2',
        'http://mock-controller3'
    ]

    def mock_ping_url(url, api_key, auth_token_type, logger=None):
        return url == 'http://mock-controller2'

    monkeypatch.setattr(
        'agents_infra.utils.network.ping_url',
        mock_ping_url
    )

    result = find_first_healthy_url(
        urls,
        api_key=None,
        auth_token_type='mock-token',
        logger=logging.getLogger('test')
    )

    assert result == 'http://mock-controller2'


@mock.patch('socket.create_connection')
def test_is_tcp_reachable_success(mock_create_conn):
    result = is_tcp_reachable('http://example.com')
    assert result is True
    assert mock_create_conn.called


@mock.patch('socket.create_connection', side_effect=socket.error)
def test_is_tcp_reachable_failure(mock_create_conn):
    result = is_tcp_reachable('http://example.com')
    assert result is False
    assert mock_create_conn.called


@mock.patch('urllib2.urlopen')
def test_check_http_health_success(mock_urlopen):
    mock_response = mock.Mock()
    mock_response.read.return_value = json.dumps({'status': 'healthy'})
    mock_urlopen.return_value = mock_response

    result = check_http_health(
        'http://example.com',
        api_key='abc',
        auth_token_type='Bearer'
    )
    assert result is True
    assert mock_urlopen.called


@mock.patch('urllib2.urlopen')
def test_check_http_health_failure_status_not_healthy(mock_urlopen):
    mock_response = mock.Mock()
    mock_response.read.return_value = json.dumps({'status': 'unhealthy'})
    mock_urlopen.return_value = mock_response

    result = check_http_health('http://example.com')
    assert result is False


@mock.patch('urllib2.urlopen', side_effect=urllib2.URLError('mock error'))
def test_check_http_health_url_error(mock_urlopen):
    result = check_http_health('http://example.com')
    assert result is False


@mock.patch('urllib2.urlopen', side_effect=socket.timeout)
def test_check_http_health_timeout(mock_urlopen):
    result = check_http_health('http://example.com')
    assert result is False


@mock.patch(
    'agents_infra.utils.network.is_tcp_reachable',
    return_value=True
)
@mock.patch(
    'agents_infra.utils.network.check_http_health',
    return_value=True
)
def test_ping_url_success(mock_health, mock_tcp):
    result = ping_url(
        'http://example.com',
        api_key='abc',
        auth_token_type='Bearer'
    )
    assert result is True


@mock.patch(
    'agents_infra.utils.network.is_tcp_reachable',
    return_value=False
)
def test_ping_url_tcp_unreachable(mock_tcp):
    result = ping_url(
        'http://example.com',
        api_key='abc',
        auth_token_type='Bearer'
    )
    assert result is False


@mock.patch(
    'agents_infra.utils.network.is_tcp_reachable',
    return_value=True
)
@mock.patch(
    'agents_infra.utils.network.check_http_health',
    return_value=False
)
def test_ping_url_http_unhealthy(mock_health, mock_tcp):
    result = ping_url(
        'http://example.com',
        api_key='abc',
        auth_token_type='Bearer'
    )
    assert result is False
