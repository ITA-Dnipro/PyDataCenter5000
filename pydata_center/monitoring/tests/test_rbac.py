import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.utils.timezone import now
from monitoring.models import CommandHistory, ServerStatus
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def init_roles(db):
    call_command('init_roles')


@pytest.fixture
def viewer_user(db):
    user = User.objects.create_user(username='viewer', password='pass')
    viewer_group = Group.objects.get(name='Viewer')
    user.groups.add(viewer_group)
    return user


@pytest.fixture
def operator_user(db):
    user = User.objects.create_user(username='operator', password='pass')
    group = Group.objects.get(name='Operator')
    user.groups.add(group)
    return user


@pytest.fixture
def viewer_client(viewer_user):
    client = APIClient()
    client.force_authenticate(user=viewer_user)
    return client


@pytest.fixture
def operator_client(operator_user):
    client = APIClient()
    client.force_authenticate(user=operator_user)
    return client


@pytest.mark.django_db
class TestRBACPermissions:
    """
    Viewer should be forbidden to POST
    server status data.
    """

    @classmethod
    def setup_class(cls):
        cls.url = '/api/v1/server/status/'

    def test_viewer_role_is_forbidden_to_post_status_data(self, viewer_client):
        payload = {
            'hostname': 'agent001',
            'ip': '192.168.1.1',
            'uptime': 123.45,
            'timestamp': '2025-06-19T10:00:00Z',
            'healthy': 'yes',
            'server_name': 'TestServer',
            'os': 'Linux'
        }

        response = viewer_client.post(self.url, data=payload, format='json')
        assert response.status_code == 403


@pytest.mark.django_db
class TestCommandHistoryRBAC:
    """
    Test RBAC rules for CommandHistoryViewSet
    (Viewer and Operator).
    """

    @classmethod
    def setup_class(cls):
        cls.url = '/api/v1/commands/'

    def test_viewer_can_list_commands(self, viewer_client):
        response = viewer_client.get(self.url)
        assert response.status_code == 200

    def test_viewer_cannot_create_command(self, viewer_client):
        payload = {
            'hostname': 'agent001',
            'command': 'ls'
        }
        response = viewer_client.post(self.url, data=payload)
        assert response.status_code == 403

    def test_operator_can_create_command(self, operator_client):
        payload = {
            'hostname': 'agent001',
            'command': 'ls'
        }
        response = operator_client.post(self.url, data=payload)
        assert response.status_code == 201
        assert response.data['status'] == 'pending'

    def test_viewer_cannot_patch_command(self, viewer_client, db):
        command = CommandHistory.objects.create(
            hostname='agent001',
            command='uptime',
            status='pending'
        )
        url = f'{self.url}{command.id}/'
        response = viewer_client.patch(url, data={'status': 'done'})
        assert response.status_code == 403

    def test_operator_can_patch_command(self, operator_client, db):
        command = CommandHistory.objects.create(
            hostname='agent001',
            command='uptime',
            status='pending'
        )
        url = f'{self.url}{command.id}/'
        response = operator_client.patch(url, data={'status': 'done'})
        assert response.status_code == 200
        assert response.data['status'] == 'done'

    def test_viewer_cannot_delete_command(self, viewer_client, db):
        command = CommandHistory.objects.create(
            hostname='agent001',
            command='reboot',
            status='done'
        )
        url = f'{self.url}{command.id}/'
        response = viewer_client.delete(url)
        assert response.status_code == 403

    def test_operator_can_delete_command(self, operator_client, db):
        command = CommandHistory.objects.create(
            hostname='agent001',
            command='reboot',
            status='done'
        )
        url = f'{self.url}{command.id}/'
        response = operator_client.delete(url)
        assert response.status_code == 204
