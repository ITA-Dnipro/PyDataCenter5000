import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from monitoring.models import CommandHistory
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def setup_roles():
    call_command('init_roles')


@pytest.mark.django_db
def test_operator_can_submit_command():
    user = User.objects.create_user(username='operator', password='pass')
    operator_group, _ = Group.objects.get_or_create(name='Operator')
    user.groups.add(operator_group)

    command = CommandHistory.objects.create(
        hostname='agent001',
        command='ls -la',
        status='pending'
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        '/api/v1/command/result/', data={'id': command.id, 'status': 'done'},
        format='json'
    )

    assert response.status_code == 200
    command.refresh_from_db()
    assert response.data['status'] == 'done'


@pytest.mark.django_db
def test_admin_can_submit_command():
    user = User.objects.create_user(username='admin', password='pass')
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user.groups.add(admin_group)

    command = CommandHistory.objects.create(
        hostname='agent001',
        command='uptime',
        status='pending'
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        '/api/v1/command/result/', data={'id': command.id, 'status': 'done'},
        format='json'
    )
    assert response.status_code == 200
    command.refresh_from_db()
    assert response.data['status'] == 'done'
