import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.utils.timezone import now
from monitoring.models import ServerStatus
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
def viewer_client(viewer_user):
    client = APIClient()
    client.force_authenticate(user=viewer_user)
    return client


@pytest.mark.django_db
class TestRBACPermissions:

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

    @pytest.mark.skip(reason='GET not supported by function-based view')
    def test_viewer_role_can_get_status_list(self, viewer_client):
        ServerStatus.objects.create(
            hostname='agent001',
            ip='192.168.1.1',
            uptime=123,
            timestamp=now(),
            healthy=True,
            server_name='TestServer',
            os='Linux'
        )
        response = viewer_client.get(self.url)
        assert response.status_code == 200

    @pytest.mark.skip(reason='PATCH not supported by function-based view')
    def test_viewer_role_cannot_patch_status(self, viewer_client):
        status = ServerStatus.objects.create(
            hostname='agent001',
            ip='192.168.1.1',
            uptime=123,
            timestamp=now(),
            healthy=True,
            server_name='TestServer',
            os='Linux'
        )
        url = f'{self.url}{status.id}/'
        response = viewer_client.patch(url, data={'uptime': 999})
        assert response.status_code == 403

    @pytest.mark.skip(reason='DELETE not supported by function-based view')
    def test_viewer_role_cannot_delete_status(self, viewer_client):
        status = ServerStatus.objects.create(
            hostname='agent001',
            ip='192.168.1.1',
            uptime=123,
            timestamp=now(),
            healthy=True,
            server_name='TestServer',
            os='Linux'
        )
        url = f'{self.url}{status.id}/'
        response = viewer_client.delete(url)
        assert response.status_code == 403
