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
from django.urls import reverse
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

    @pytest.mark.parametrize(
        'healthy, should_trigger',
        [(False, True), (True, False)],
    )
    def test_status_alert_behavior(
            self,
            authenticated_client,
            healthy,
            should_trigger
    ):
        """Tests both healthy and unhealthy status alert logic."""
        hostname = 'agent_fail' if not healthy else 'agent_ok'
        payload = {
            'hostname': hostname,
            'ip': '127.0.0.1',
            'uptime': 123,
            'healthy': healthy,
            'timestamp': datetime.now().isoformat(),
            'os': 'Linux',
            'server_name': hostname,
        }
        url = reverse('monitoring:receive_status')

        if should_trigger:
            path_to_mock = 'monitoring.views.alert_if_unhealthy'
            with patch(path_to_mock) as mock_alert:
                response = authenticated_client.post(
                    url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 201
                mock_alert.assert_called_once_with(hostname, healthy)
        else:
            path_to_mock = 'monitoring.alerts.send_discord_alert'
            with patch(path_to_mock) as mock_send_alert:
                response = authenticated_client.post(
                    url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 201
                mock_send_alert.assert_not_called()


class TestCommandHistoryAPI:
    """Tests for the command history endpoints."""

    @pytest.mark.parametrize(
        'status, result, should_trigger',
        [
            ('failed', 'Error occurred', True),
            ('done', 'Success', False),
        ],
    )
    def test_command_update_alert_behavior(
            self, authenticated_client, status, result, should_trigger
    ):
        """Tests alert behavior for command updates."""
        command = CommandHistory.objects.create(
            hostname='agent-x',
            command='ls'
        )
        payload = {'status': status, 'result': result}
        url = reverse('monitoring:commandhistory-detail', args=[command.id])

        if should_trigger:
            path_to_mock = 'monitoring.views.alert_if_command_failed'
            with patch(path_to_mock) as mock_alert:
                response = authenticated_client.patch(
                    url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 200
                mock_alert.assert_called_once_with('agent-x', result)
        else:
            path_to_mock = 'monitoring.alerts.send_discord_alert'
            with patch(path_to_mock) as mock_send_alert:
                response = authenticated_client.patch(
                    url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 200
                mock_send_alert.assert_not_called()

    @pytest.mark.parametrize(
        'status, result, should_trigger',
        [
            ('failed', 'Command FAILED', True),
            ('done', 'Everything is fine', False),
        ],
    )
    def test_command_submit_alert_behavior(
            self, authenticated_client, status, result, should_trigger
    ):
        """Tests alert behavior for command result submissions."""
        command = CommandHistory.objects.create(
            hostname='agent-ok',
            command='whoami'
        )
        payload = {'id': command.id, 'status': status, 'result': result}
        url = reverse('monitoring:submit_command_result')

        if should_trigger:
            path_to_mock = 'monitoring.views.alert_if_command_failed'
            with patch(path_to_mock) as mock_alert:
                response = authenticated_client.patch(
                    url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 200
                mock_alert.assert_called_once_with('agent-ok', result)
        else:
            path_to_mock = 'monitoring.alerts.send_discord_alert'
            with patch(path_to_mock) as mock_send_alert:
                response = authenticated_client.patch(
                    url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 200
                mock_send_alert.assert_not_called()
