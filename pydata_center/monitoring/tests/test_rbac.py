import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_viewer_cannot_post_status():
    user = User.objects.create_user(username='viewer', password='pass')
    viewer_group = Group.objects.get(name='Viewer')
    user.groups.add(viewer_group)

    client = APIClient()
    client.force_authenticate(user=user)

    payload = {
        'hostname': 'agent001',
        'ip': '192.168.1.1',
        'uptime': 123.45,
        'timestamp': '2025-06-19T10:00:00Z',
        'healthy': 'yes',
        'server_name': 'TestServer',
        'os': 'Linux'
    }

    response = client.post(
        '/api/v1/server/status/', data=payload, format='json'
    )

    assert response.status_code == 403
