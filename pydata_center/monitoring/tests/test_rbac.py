import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
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

    def setup_method(self):
        self.url = '/api/v1/server/status/'

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
