"""
These tests require that the PostgreSQL user has permission to create test
databases. If you encounter the following error during local test execution:
psycopg2.errors.InsufficientPrivilege: permission denied to create database,
connect to Postgre as a superuser and run: ALTER USER your_username CREATEDB;
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from monitoring.models import CommandHistory
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client(db):
    """
    Create a user and return an authenticated API client.
    """
    user = User.objects.create_user(username='test_user')
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestServerStatusAPI:
    """Tests for the server status endpoint."""

    def test_unhealthy_status_triggers_alert(self, authenticated_client):
        """Test that an 'unhealthy' status triggers an alert."""
        payload = {
            'hostname': 'agent-1',
            'ip': '192.168.0.1',
            'uptime': 12345,
            'healthy': False,
            'timestamp': datetime.now().isoformat(),
            'os': 'Linux',
            'server_name': 'agent_1',
        }

        with patch('monitoring.views.alert_if_unhealthy') as mock_alert:
            response = authenticated_client.post(
                '/api/v1/server/status/', data=payload, format='json'
            )
            assert response.status_code == 201
            mock_alert.assert_called_once_with('agent-1', False)

    def test_healthy_status_is_ignored(self, authenticated_client):
        """Test that a 'healthy' status is ignored and sends no alert."""
        payload = {
            'hostname': 'agent-ok',
            'ip': '10.0.0.1',
            'uptime': 999,
            'healthy': True,
            'timestamp': datetime.now().isoformat(),
            'os': 'Windows',
            'server_name': 'agent_ok',
        }

        with patch('monitoring.alerts.send_discord_alert') as mock_send_alert:
            response = authenticated_client.post(
                '/api/v1/server/status/', data=payload, format='json'
            )
            assert response.status_code == 201
            mock_send_alert.assert_not_called()


class TestCommandHistoryAPI:
    """Tests for the command history endpoints."""

    def test_failed_command_update_triggers_alert(self, authenticated_client):
        """
        Test that updating a command to 'failed' status triggers an alert.
        """
        command = CommandHistory.objects.create(
            hostname='agent-2',
            command='ls'
        )
        payload = {'status': 'failed', 'result': 'Error occurred'}
        url = f'/api/v1/commands/{command.id}/'

        with patch('monitoring.views.alert_if_command_failed') as mock_alert:
            response = authenticated_client.patch(
                url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_alert.assert_called_once_with('agent-2', 'Error occurred')

    def test_successful_command_update_is_ignored(self, authenticated_client):
        """Test that a successful command update is ignored."""
        command = CommandHistory.objects.create(
            hostname='agent-ok',
            command='whoami'
        )
        payload = {'status': 'done', 'result': 'Success'}
        url = f'/api/v1/commands/{command.id}/'

        with patch('monitoring.alerts.send_discord_alert') as mock_send_alert:
            response = authenticated_client.patch(
                url,
                data=payload, format='json'
            )
            assert response.status_code == 200
            mock_send_alert.assert_not_called()

    def test_failed_command_submit_triggers_alert(self, authenticated_client):
        """Test that submitting a 'failed' command result triggers an alert."""
        command = CommandHistory.objects.create(
            hostname='agent-3',
            command='uptime'
        )
        payload = {
            'id': command.id,
            'status': 'failed',
            'result': 'Command FAILED'
        }

        with patch('monitoring.views.alert_if_command_failed') as mock_alert:
            response = authenticated_client.patch(
                '/api/v1/command/result/', data=payload, format='json'
            )
            assert response.status_code == 200
            mock_alert.assert_called_once_with('agent-3', 'Command FAILED')

    def test_successful_command_submit_is_ignored(self, authenticated_client):
        """Test that submitting a successful command result is ignored."""
        command = CommandHistory.objects.create(
            hostname='agent-ok',
            command='ping'
        )
        payload = {
            'id': command.id,
            'status': 'done',
            'result': 'Everything is fine'
        }

        with patch('monitoring.alerts.send_discord_alert') as mock_send_alert:
            response = authenticated_client.patch(
                '/api/v1/command/result/', data=payload, format='json'
            )
            assert response.status_code == 200
            mock_send_alert.assert_not_called()
