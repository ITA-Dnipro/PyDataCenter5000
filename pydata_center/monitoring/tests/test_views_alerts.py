"""
These tests require that the PostgreSQL user has permission to create test
databases. If you encounter the following error during local test execution:
psycopg2.errors.InsufficientPrivilege: permission denied to create database,
connect to Postgre as a superuser and run: ALTER USER your_username CREATEDB;
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse
from monitoring.authentication import AgentTokenAuthentication
from monitoring.models import CommandHistory
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client(db):
    """
    Create a user, add it to Operator group
    and return an authenticated API client.
    """
    user = User.objects.create_user(username='test_user')
    # add user to Operator group
    operator_group, _ = Group.objects.get_or_create(name='Operator')
    permission = Permission.objects.get(codename='add_serverstatus')
    operator_group.permissions.add(permission)
    user.groups.add(operator_group)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestServerStatusAPI:
    """Tests for the server status endpoint."""

    def setup_method(self, method):
        self.hostname = 'mock-agent'
        self.url = reverse('monitoring:receive_status')
        self.token = 'mock.jwt.token'

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # Patch authentication to return a mock agent user
        self._auth_patcher = patch.object(
            AgentTokenAuthentication,
            'authenticate',
            return_value=(self._mock_user(), None)
        )
        self._auth_patcher.start()

    def teardown_method(self, method):
        self._auth_patcher.stop()

    def _mock_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.is_active = True
        user.is_agent = True
        user.has_perm.return_value = True
        return user

    @pytest.mark.parametrize(
        'healthy, should_trigger',
        [(False, True), (True, False)],
    )
    def test_status_alert_behavior(self, healthy, should_trigger):
        """Test healthy/unhealthy status triggers correct alert behavior."""
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

        if should_trigger:
            with patch(
                'monitoring.views.alert_if_unhealthy'
            ) as mock_alert:
                response = self.client.post(
                    self.url,
                    data=payload,
                    format='json'
                )
                assert response.status_code == 201
                mock_alert.assert_called_once_with(
                    hostname,
                    healthy
                )
        else:
            with patch(
                'monitoring.alerts.send_discord_alert'
            ) as mock_send_alert:
                response = self.client.post(
                    self.url,
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
    def test_bad_payloads_return_400(self, invalid_payload, test_id):
        """Test that bad payloads return 400 status."""
        url = reverse('monitoring:receive_status')
        response = self.client.post(
            url,
            data=invalid_payload,
            format='json'
        )
        assert response.status_code == 400

    def test_unauthenticated_access_is_denied(self):
        """Test unauthenticated access is rejected."""
        client = APIClient()
        url = reverse('monitoring:receive_status')
        response = client.post(url, data={}, format='json')
        assert response.status_code in (400, 401, 403)


class TestCommandHistoryAPI:
    """
    Tests for the command history endpoints.
    """

    def setup_method(self, method):
        self.command = CommandHistory.objects.create(
            hostname='agent-setup',
            type='linux',
            params={'shell': 'initial_command'},
            notify_on_success=False
        )
        self.detail_url = reverse(
            'monitoring:commandhistory-detail',
            args=[self.command.id]
        )
        self.submit_url = reverse('monitoring:submit_command_result')

    def test_update_to_failed_triggers_failure_alert(
            self,
            authenticated_client
    ):
        """
        Test that updating a command to 'failed' triggers a failure alert.
        """
        payload = {'status': 'failed', 'result': 'Update failed unexpectedly'}

        path_to_mock = 'monitoring.views.alert_if_command_failed'
        with patch(path_to_mock) as mock_failure_alert:
            response = authenticated_client.patch(
                self.detail_url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_failure_alert.assert_called_once_with(
                self.command.hostname,
                'Update failed unexpectedly'
            )

    def test_update_to_done_is_ignored_by_default(self, authenticated_client):
        """
        Test a successful update is ignored if notify_on_success is False.
        """
        payload = {'status': 'done', 'result': 'Success'}

        with patch('monitoring.alerts.send_discord_alert') as mock_any_alert:
            response = authenticated_client.patch(
                self.detail_url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_any_alert.assert_not_called()

    def test_update_to_done_with_flag_triggers_success_alert(
            self,
            authenticated_client
    ):
        """
        Test a successful update triggers an alert if notify_on_success is True
        """
        self.command.notify_on_success = True
        self.command.save()
        payload = {'status': 'done', 'result': 'Critical task succeeded'}

        with patch('monitoring.views.alert_on_success') as mock_success_alert:
            response = authenticated_client.patch(
                self.detail_url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_success_alert.assert_called_once_with(
                self.command.hostname,
                'Critical task succeeded'
            )

    def test_submit_failed_result_triggers_failure_alert(
            self,
            authenticated_client
    ):
        """
        Test that submitting a 'failed' result triggers a failure alert.
        """
        payload = {
            'id': self.command.id,
            'status': 'failed',
            'result': 'Submission failed'
        }

        path_to_mock = 'monitoring.views.alert_if_command_failed'
        with patch(path_to_mock) as mock_failure_alert:
            response = authenticated_client.patch(
                self.submit_url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_failure_alert.assert_called_once_with(
                self.command.hostname,
                'Submission failed'
            )

    def test_submit_done_result_is_ignored_by_default(
            self,
            authenticated_client
    ):
        """
        Test a successful submission is ignored if notify_on_success is False.
        """
        payload = {
            'id': self.command.id,
            'status': 'done',
            'result': 'All good'
        }

        with patch('monitoring.alerts.send_discord_alert') as mock_any_alert:
            response = authenticated_client.patch(
                self.submit_url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_any_alert.assert_not_called()

    def test_submit_done_result_with_flag_triggers_success_alert(
            self,
            authenticated_client
    ):
        """
        Test a successful submission triggers an alert
        if notify_on_success is True.
        """
        self.command.notify_on_success = True
        self.command.save()
        payload = {
            'id': self.command.id,
            'status': 'done',
            'result': 'Important task done'
        }

        with patch('monitoring.views.alert_on_success') as mock_success_alert:
            response = authenticated_client.patch(
                self.submit_url,
                data=payload,
                format='json'
            )
            assert response.status_code == 200
            mock_success_alert.assert_called_once_with(
                self.command.hostname,
                'Important task done'
            )

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
        response = authenticated_client.patch(
            self.submit_url,
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
        payload = {
            'id': self.command.id,
            'status': 'this-is-not-a-valid-status',
            'result': 'some result',
        }
        response = authenticated_client.patch(
            self.submit_url,
            data=payload,
            format='json'
        )
        assert response.status_code == 400

    def test_update_unauthenticated_is_denied(self, db):
        """
        Test that unauthenticated access to the command update
        endpoint is rejected.
        """
        client = APIClient()
        command = CommandHistory.objects.create(
            hostname='test',
            type='linux',
            params={'shell': 'cmd'},
        )
        url = reverse('monitoring:commandhistory-detail', args=[command.id])
        response = client.patch(url, data={})
        assert response.status_code in (401, 403)

    def test_submit_result_unauthenticated_is_denied(self):
        """
        Test that unauthenticated access to the command result submission
        endpoint is rejected.
        """
        client = APIClient()
        url = reverse('monitoring:submit_command_result')
        response = client.patch(url, data={'id': 999})
        assert response.status_code in (401, 403)
