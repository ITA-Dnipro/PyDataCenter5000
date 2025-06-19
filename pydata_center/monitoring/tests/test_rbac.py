import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient


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


class TestRBACPermissions:

    def setup_method(self):
        self.url = '/api/v1/server/status/'

    def test_viewer_role_is_forbidden_to_post_status_data(self, viewer_client):
        """
        Viewer users should not be able to submit server status.
        Expected: 403 Forbidden.
        """
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
