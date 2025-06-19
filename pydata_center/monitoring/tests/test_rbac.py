import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from monitoring.models import CommandHistory
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def setup_roles():
    call_command('init_roles')


@pytest.fixture
def operator_user():
    user = User.objects.create_user(username='operator', password='pass')
    operator_group = Group.objects.get(name='Operator')
    user.groups.add(operator_group)
    return user


@pytest.fixture
def admin_user():
    user = User.objects.create_user(username='admin', password='pass')
    admin_group = Group.objects.get(name='Admin')
    user.groups.add(admin_group)
    return user


@pytest.mark.django_db
def test_operator_can_access_submit_command_endpoint(operator_user):
    command = CommandHistory.objects.create(
        hostname='agent001',
        command='ls -la',
        status='pending'
    )

    client = APIClient()
    client.force_authenticate(user=operator_user)

    response = client.patch(
        '/api/v1/command/result/',
        data={'id': command.id},
        format='json'
    )

    assert response.status_code == 200
    command.refresh_from_db()
    assert command.status == 'pending'
    assert response.data['status'] == 'pending'


@pytest.mark.django_db
def test_admin_can_access_submit_command_endpoint(admin_user):
    command = CommandHistory.objects.create(
        hostname='agent001',
        command='uptime',
        status='pending'
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)

    response = client.patch(
        '/api/v1/command/result/',
        data={'id': command.id},
        format='json'
    )

    assert response.status_code == 200
    command.refresh_from_db()
    assert command.status == 'pending'
    assert response.data['status'] == 'pending'