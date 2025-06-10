from unittest.mock import patch

from monitoring.models import CommandHistory
from rest_framework.test import APIClient


@patch('monitoring.views.alert_if_unhealthy')
def test_receive_status_triggers_alert(mock_alert):
    client = APIClient()
    payload = {
        'hostname': 'agent-1',
        'ip': '192.168.0.1',
        'uptime': 12345,
        'healthy': False
    }
    response = client.post('/api/v1/status/', data=payload, format='json')
    assert response.status_code == 201
    mock_alert.assert_called_once_with('agent-1', False)


@patch('monitoring.views.alert_if_unhealthy')
def test_receive_status_ignores_healthy(mock_alert):
    client = APIClient()
    payload = {
        'hostname': 'agent-ok',
        'ip': '10.0.0.1',
        'uptime': 999,
        'healthy': True
    }
    response = client.post('/api/v1/status/', data=payload, format='json')
    assert response.status_code == 201
    mock_alert.assert_not_called()


@patch('monitoring.views.alert_if_command_failed')
def test_partial_update_triggers_alert(mock_alert, db):
    command = CommandHistory.objects.create(
        hostname='agent-2',
        command='ls',
        status='pending',
        result=''
    )
    client = APIClient()
    payload = {
        'status': 'failed',
        'result': 'Error occurred'
    }
    url = f'/api/v1/commands/{command.id}/'
    response = client.patch(url, data=payload, format='json')
    assert response.status_code == 200
    mock_alert.assert_called_once_with('agent-2', 'Error occurred')


@patch('monitoring.views.alert_if_command_failed')
def test_partial_update_ignores_success(mock_alert, db):
    command = CommandHistory.objects.create(
        hostname='agent-ok',
        command='whoami',
        status='pending',
        result=''
    )
    client = APIClient()
    payload = {
        'status': 'done',
        'result': 'Success'
    }
    url = f'/api/v1/commands/{command.id}/'
    response = client.patch(url, data=payload, format='json')
    assert response.status_code == 200
    mock_alert.assert_not_called()


@patch('monitoring.views.alert_if_command_failed')
def test_submit_command_result_triggers_alert(mock_alert, db):
    command = CommandHistory.objects.create(
        hostname='agent-3',
        command='uptime',
        status='pending',
        result=''
    )
    client = APIClient()
    payload = {
        'id': command.id,
        'status': 'failed',
        'result': 'Command FAILED'
    }
    response = client.patch(
        '/api/v1/command-result/',
        data=payload,
        format='json'
    )
    assert response.status_code == 200
    mock_alert.assert_called_once_with('agent-3', 'Command FAILED')


@patch('monitoring.views.alert_if_command_failed')
def test_submit_command_result_ignores_clean_result(mock_alert, db):
    command = CommandHistory.objects.create(
        hostname='agent-ok',
        command='ping',
        status='pending',
        result=''
    )
    client = APIClient()
    payload = {
        'id': command.id,
        'status': 'done',
        'result': 'Everything is fine'
    }
    response = client.patch(
        '/api/v1/command-result/',
        data=payload,
        format='json'
    )
    assert response.status_code == 200
    mock_alert.assert_not_called()
