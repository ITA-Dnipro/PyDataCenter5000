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

    @pytest.mark.parametrize(
        'invalid_payload, test_id',
        [
            (
                    {'hostname': 'agent-missing-fields'},
                    'missing_required_fields',
            ),
            (
                    {
                        'hostname': 'agent-invalid-data',
                        'ip': 'not_an_ip_address',
                        'uptime': 'not_a_number',
                        'healthy': 'maybe',
                        'timestamp': 'not_a_date',
                        'os': 'Linux',
                        'server_name': 'agent-invalid-data',
                    },
                    'invalid_data_types',
            ),
        ],
        ids=['test_with_missing_fields', 'test_with_invalid_data'],
    )
    def test_bad_payloads_return_400(
            self, authenticated_client, invalid_payload, test_id
    ):
        """Test that various types of bad payloads return a 400 status."""
        url = reverse('monitoring:receive_status')
        response = authenticated_client.post(
            url,
            data=invalid_payload,
            format='json'
        )
        assert response.status_code == 400


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

    def test_update_nonexistent_command_returns_404(
            self,
            authenticated_client
    ):
        """
        Test that trying to update a command that does not exist returns 404.
        """
        url = reverse('monitoring:commandhistory-detail', args=[99999])
        payload = {'status': 'done', 'result': 'This should fail'}

        response = authenticated_client.patch(url, data=payload, format='json')

        assert response.status_code == 404

    @pytest.mark.parametrize(
        'bad_payload, test_id',
        [
            (
                    {'id': 99999, 'status': 'done'},
                    'nonexistent_id',
            ),
            (
                    {'status': 'done', 'result': 'some result'},
                    'missing_id',
            ),
        ],
        ids=['nonexistent_id', 'missing_id'],
    )
    def test_submit_result_with_bad_id_returns_404(
            self, authenticated_client, bad_payload, test_id
    ):
        """
        Test that submitting a result with a missing or nonexistent command ID
        returns 404.
        """
        url = reverse('monitoring:submit_command_result')

        response = authenticated_client.patch(
            url,
            data=bad_payload,
            format='json'
        )

        assert response.status_code == 404

    def test_submit_result_with_invalid_status_returns_400(
            self, authenticated_client
    ):
        """
        Test that submitting a result with an invalid status string returns 400
        """
        command = CommandHistory.objects.create(
            hostname='agent-x',
            command='test'
        )
        url = reverse('monitoring:submit_command_result')
        payload = {
            'id': command.id,
            'status': 'this-is-not-a-valid-status',
            'result': 'some result',
        }

        response = authenticated_client.patch(url, data=payload, format='json')

        assert response.status_code == 400
