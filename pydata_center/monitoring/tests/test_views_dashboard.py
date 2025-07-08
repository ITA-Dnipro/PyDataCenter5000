from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse
from django.utils.timezone import now
from monitoring.models import ServerStatus


@pytest.fixture
def authenticated_client(client, db):
    user = User.objects.create_user(username='testuser', password='pass')
    operator_group, _ = Group.objects.get_or_create(name='Operator')
    permission = Permission.objects.get(codename='view_serverstatus')
    operator_group.permissions.add(permission)
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
        'timestamp_delta, expected_offline_status',
        [
            (timedelta(seconds=10), False),
            (timedelta(minutes=10), True),
        ]
    )
    def test_dashboard_online_offline_status(
            self,
            authenticated_client,
            url,
            timestamp_delta,
            expected_offline_status
    ):
        """
        Tests if an agent is correctly displayed as online or offline
        by checking both context data and the rendered HTML class.
        """
        ServerStatus.objects.create(
            hostname='vm-test-agent',
            ip='10.0.0.1',
            uptime=100,
            healthy=True,
            timestamp=now() - timestamp_delta
        )
        response = authenticated_client.get(url)
        assert response.status_code == 200

        agents_in_context = response.context['agents']
        assert len(agents_in_context) == 1
        assert agents_in_context[0]['offline'] is expected_offline_status

        soup = BeautifulSoup(response.content, 'html.parser')

        row = soup.find('td', string='vm-test-agent').parent
        assert row is not None

        has_offline_class = 'offline' in row.get('class', [])
        assert has_offline_class == expected_offline_status

    def test_dashboard_displays_multiple_agents(
            self,
            authenticated_client,
            url
    ):
        """
        Tests that the dashboard correctly lists multiple agents with
        different statuses.
        """
        ServerStatus.objects.create(
            hostname='vm-online-01',
            ip='10.0.0.1',
            uptime=100,
            healthy=True,
            timestamp=now()
        )
        ServerStatus.objects.create(
            hostname='vm-offline-02',
            ip='10.0.0.2',
            uptime=200,
            healthy=True,
            timestamp=now() - timedelta(minutes=5)
        )

        response = authenticated_client.get(url)
        content = response.content.decode()

        assert response.status_code == 200
        assert len(response.context['agents']) == 2
        assert 'vm-online-01' in content
        assert 'vm-offline-02' in content
        assert content.count('class="offline"') == 1

    def test_dashboard_displays_tags_correctly(
            self,
            authenticated_client,
            url
    ):
        """
        Tests that agent tags are correctly rendered in the dashboard HTML.
        """
        ServerStatus.objects.create(
            hostname='agent-with-tags',
            ip='10.0.0.1',
            uptime=100,
            healthy=True,
            timestamp=now(),
            tags={'env': 'prod', 'role': 'api'}
        )
        ServerStatus.objects.create(
            hostname='agent-no-tags',
            ip='10.0.0.2',
            uptime=200,
            healthy=True,
            timestamp=now(), tags={}
        )

        response = authenticated_client.get(url)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, 'html.parser')

        row_with_tags = soup.find('td', string='agent-with-tags').parent
        rendered_tags = {
            tag.text.strip() for tag in row_with_tags.select('span.tag')
        }
        assert rendered_tags == {'env: prod', 'role: api'}

        row_no_tags = soup.find('td', string='agent-no-tags').parent
        tags_cell = row_no_tags.find('td', class_='tags-cell')
        assert tags_cell.text.strip() == '-'

    def test_dashboard_filtering_works(
            self,
            authenticated_client,
            url
    ):
        """
        Tests that the view correctly filters agents based on query parameters
        and renders only the filtered results.
        """
        ServerStatus.objects.create(
            hostname='prod-web',
            ip='10.0.0.1',
            uptime=100,
            healthy=True,
            timestamp=now(),
            tags={'env': 'production', 'role': 'web'}
        )
        ServerStatus.objects.create(
            hostname='staging-web',
            ip='10.0.0.2',
            uptime=200,
            healthy=True,
            timestamp=now(),
            tags={'env': 'staging', 'role': 'web'}
        )

        filtered_url = url + '?tag_env=production'
        response = authenticated_client.get(filtered_url)
        content = response.content.decode()

        assert response.status_code == 200

        assert 'prod-web' in content
        assert 'staging-web' not in content

        assert len(response.context['agents']) == 1
        assert response.context['agents'][0]['hostname'] == 'prod-web'

    def test_dashboard_combined_filtering(
            self,
            authenticated_client,
            url
    ):
        """
        Tests that the dashboard view correctly handles combined filtering
        from multiple query parameters.
        """
        ServerStatus.objects.create(
            hostname='multi-filter-prod',
            ip='10.0.0.3',
            uptime=100,
            healthy=True,
            timestamp=now(),
            tags={'env': 'production', 'role': 'db'}
        )
        ServerStatus.objects.create(
            hostname='wrong-host-prod',
            ip='10.0.0.4',
            uptime=100,
            healthy=True,
            timestamp=now(),
            tags={'env': 'production', 'role': 'db'}
        )
        ServerStatus.objects.create(
            hostname='multi-filter-staging',
            ip='10.0.0.5',
            uptime=100,
            healthy=True,
            timestamp=now(),
            tags={'env': 'staging', 'role': 'db'}
        )

        filtered_url = url + '?hostname=multi-filter&tag_env=production'
        response = authenticated_client.get(filtered_url)
        assert response.status_code == 200

        agents_in_context = response.context['agents']
        assert len(agents_in_context) == 1
        assert agents_in_context[0]['hostname'] == 'multi-filter-prod'

        content = response.content.decode()
        assert 'multi-filter-prod' in content
        assert 'wrong-host-prod' not in content
        assert 'multi-filter-staging' not in content

    def test_dashboard_filter_form_preserves_state(
            self,
            authenticated_client,
            url
    ):
        """
        Tests that the filter form fields are pre-filled with the values
        from the GET request parameters.
        """
        filtered_url = url + '?hostname=server&tag_role=db'
        response = authenticated_client.get(filtered_url)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, 'html.parser')

        hostname_input = soup.select_one('input[name="hostname"]')
        tag_role_input = soup.select_one('input[name="tag_role"]')

        assert hostname_input is not None
        assert tag_role_input is not None

        assert hostname_input.get('value') == 'server'
        assert tag_role_input.get('value') == 'db'
