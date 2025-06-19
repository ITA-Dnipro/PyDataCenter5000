from datetime import timedelta

import pytest
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils.timezone import now
from monitoring.models import ServerStatus


@pytest.fixture
def authenticated_client(client, db):
    user = User.objects.create_user(username='testuser', password='pass')
    operator_group, _ = Group.objects.get_or_create(name='Operator')
    user.groups.add(operator_group)
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestDashboardView:
    """Test suite for the dashboard_view."""

    @pytest.fixture
    def url(self):
        return reverse('monitoring:dashboard')

    def test_dashboard_smoke_test(self, authenticated_client, url):
        """
        Tests that the dashboard page loads correctly, uses the right template,
        and contains key static text when no agents exist.
        """
        response = authenticated_client.get(url)
        content = response.content.decode()

        assert response.status_code == 200
        assert 'monitoring/dashboard.html' in [
            template.name
            for template in response.templates
        ]
        assert 'Agent Dashboard' in content
        assert 'No agent data available' in content

    @pytest.mark.parametrize(
        'timestamp_delta, expected_offline_status, expected_class',
        [
            (timedelta(seconds=10), False, None),
            (timedelta(minutes=10), True, 'class="offline"'),
        ]
    )
    def test_dashboard_online_offline_status(
            self,
            authenticated_client,
            url,
            timestamp_delta,
            expected_offline_status,
            expected_class
    ):
        """
        Tests if an agent is correctly displayed as online or offline
        by checking both context data and the rendered HTML class.
        """
        ServerStatus.objects.create(
            hostname='vm-test-agent', ip='10.0.0.1', uptime=100, healthy=True,
            timestamp=now() - timestamp_delta
        )
        response = authenticated_client.get(url)
        content = response.content.decode()

        assert response.status_code == 200

        agents_in_context = response.context['agents']
        assert len(agents_in_context) == 1
        assert agents_in_context[0]['offline'] is expected_offline_status

        assert 'vm-test-agent' in content
        if expected_class:
            assert expected_class in content
        else:
            assert 'class="offline"' not in content

    def test_dashboard_displays_multiple_agents(self, authenticated_client, url):
        """
        Tests that the dashboard correctly lists multiple agents with
        different statuses.
        """
        ServerStatus.objects.create(
            hostname='vm-online-01', ip='10.0.0.1', uptime=100, healthy=True,
            timestamp=now()
        )
        ServerStatus.objects.create(
            hostname='vm-offline-02', ip='10.0.0.2', uptime=200, healthy=True,
            timestamp=now() - timedelta(minutes=5)
        )

        response = authenticated_client.get(url)
        content = response.content.decode()

        assert response.status_code == 200
        assert len(response.context['agents']) == 2
        assert 'vm-online-01' in content
        assert 'vm-offline-02' in content
        assert content.count('class="offline"') == 1
