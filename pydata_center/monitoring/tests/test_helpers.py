from datetime import timedelta

import pytest
from django.utils.timezone import now
from monitoring.helpers import get_latest_agents
from monitoring.models import ServerStatus


@pytest.mark.django_db
class TestGetLatestAgents:
    """
    Test suite for the `get_latest_agents` function.
    """

    def setup_method(self, method):
        self.right_now = now()
        ServerStatus.objects.create(
            hostname='vm-01',
            ip='192.168.0.1',
            uptime=100,
            healthy=True,
            timestamp=self.right_now - timedelta(minutes=1),
            is_active=False
        )
        self.newest_vm01 = ServerStatus.objects.create(
            hostname='vm-01',
            ip='192.168.0.1',
            uptime=200,
            healthy=False,
            timestamp=self.right_now,
            is_active=True
        )

    def test_returns_only_single_latest_record_per_hostname(self):
        """
        Tests that the function returns only one, the latest, record
        per hostname, even if multiple records exist.
        """
        agents = get_latest_agents()

        assert len(agents) == 1
        latest = agents[0]
        assert latest['hostname'] == 'vm-01'
        assert latest['timestamp'] == self.newest_vm01.timestamp
        assert latest['uptime'] == self.newest_vm01.uptime
        assert latest['healthy'] is False

    def test_handles_multiple_different_hostnames(self):
        """
        Tests that the function correctly handles multiple different hostnames,
        returning the single latest record for each.
        """
        ServerStatus.objects.create(
            hostname='vm-02',
            ip='192.168.0.2',
            uptime=250,
            healthy=True,
            timestamp=self.right_now - timedelta(minutes=5),
            is_active=False
        )
        newest_vm02 = ServerStatus.objects.create(
            hostname='vm-02',
            ip='192.168.0.2',
            uptime=300,
            healthy=True,
            timestamp=self.right_now,
            is_active=True
        )
        agents = get_latest_agents()

        assert len(agents) == 2
        agents_by_hostname = {agent['hostname']: agent for agent in agents}
        assert (agents_by_hostname['vm-01']['timestamp']
                ==
                self.newest_vm01.timestamp)
        assert (agents_by_hostname['vm-02']['timestamp']
                ==
                newest_vm02.timestamp)

    def test_ignores_inactive_record_even_if_newer(self):
        """
        Test that the function selects the active record, even if an
        inactive record for the same host has a more recent timestamp.
        """
        ServerStatus.objects.all().delete()
        hostname = 'edge-case-vm'

        active_and_older = ServerStatus.objects.create(
            hostname=hostname,
            ip='192.168.10.1',
            uptime=1000,
            timestamp=self.right_now - timedelta(hours=1),
            healthy=True,
            is_active=True
        )
        ServerStatus.objects.create(
            hostname=hostname,
            ip='192.168.10.2',
            uptime=2000,
            timestamp=self.right_now,
            healthy=False,
            is_active=False
        )

        agents = get_latest_agents()

        assert len(agents) == 1, \
            'Should only return one record for the host.'

        expected_agent = {
            'hostname': active_and_older.hostname,
            'ip': active_and_older.ip,
            'uptime': active_and_older.uptime,
            'timestamp': active_and_older.timestamp,
            'healthy': active_and_older.healthy,
            'tags': active_and_older.tags,
            'offline': True
        }
        assert agents[0] == expected_agent, \
            'The returned agent must be the one marked as is_active=True.'

    def test_correctly_identifies_offline_agent(self):
        """
        Tests that an agent that has not reported recently is
        correctly flagged as `offline: True`.
        """
        ServerStatus.objects.create(
            hostname='vm-offline',
            ip='192.168.0.3',
            uptime=50,
            healthy=True,
            timestamp=self.right_now - timedelta(minutes=10)
        )
        agents = get_latest_agents()
        offline_agent = next(
            agent
            for agent in agents
            if agent['hostname'] == 'vm-offline'
        )

        assert offline_agent['offline'] is True

    def test_with_empty_db_returns_empty_list(self):
        """
        Tests that the function returns an empty list if the database is empty.
        """
        ServerStatus.objects.all().delete()
        agents = get_latest_agents()

        assert agents == []

    @pytest.mark.parametrize(
        'last_seen_ago, cutoff, expected_status',
        [
            (timedelta(seconds=30), 60, False),
            (timedelta(seconds=59), 60, False),
            (timedelta(seconds=61), 60, True),
            (timedelta(seconds=90), 60, True),
        ]
    )
    def test_offline_logic_with_parameterized_cutoff(
            self,
            last_seen_ago,
            cutoff,
            expected_status
    ):
        """
        Uses parameterization to thoroughly test the 'offline' status logic
        at its boundary conditions.
        """
        ServerStatus.objects.all().delete()

        ServerStatus.objects.create(
            hostname='vm-boundary',
            ip='192.168.0.4',
            uptime=123,
            healthy=True,
            timestamp=now() - last_seen_ago
        )
        agents = get_latest_agents(cutoff_seconds=cutoff)

        assert len(agents) == 1
        assert agents[0]['offline'] is expected_status

    def setup_filtering_data(self):
        """
        Helper method to create a standard set of agents for filtering tests.
        """
        ServerStatus.objects.all().delete()

        self.right_now = now()
        self.past_time = self.right_now - timedelta(minutes=10)

        ServerStatus.objects.create(
            hostname='web-server-01',
            ip='192.168.1.1',
            uptime=100,
            healthy=True,
            timestamp=self.right_now,
            tags={'env': 'production', 'role': 'web'}
        )

        ServerStatus.objects.create(
            hostname='db-server-01',
            ip='192.168.1.2',
            uptime=200,
            healthy=True,
            timestamp=self.right_now,
            tags={'env': 'production', 'role': 'db'}
        )

        ServerStatus.objects.create(
            hostname='staging-web-01',
            ip='192.168.2.1',
            uptime=300,
            healthy=False,
            timestamp=self.right_now,
            tags={'env': 'staging', 'role': 'web'}
        )

        ServerStatus.objects.create(
            hostname='offline-server',
            ip='192.168.3.1',
            uptime=400,
            healthy=True,
            timestamp=self.past_time
        )

    def test_filter_by_hostname_icontains(self):
        """
        Tests filtering by a partial, case-insensitive hostname.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'hostname': 'SERVER-01'}
        )

        assert len(agents) == 2

        hostnames = {agent['hostname'] for agent in agents}
        assert hostnames == {'web-server-01', 'db-server-01'}

    def test_filter_by_ip_icontains(self):
        """
        Tests filtering by a partial IP address.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'ip': '192.168.1'}
        )

        assert len(agents) == 2

        hostnames = {agent['hostname'] for agent in agents}
        assert hostnames == {'web-server-01', 'db-server-01'}

    def test_filter_by_tag_icontains_and_case_insensitivity(self):
        """
        Tests that tag filtering uses 'icontains' and is case-insensitive.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'tag_env': 'prod', 'tag_role': 'WEB'}
        )

        assert len(agents) == 1
        assert agents[0]['hostname'] == 'web-server-01'

    def test_filter_by_healthy_status(self):
        """
        Tests filtering by 'healthy' status.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'healthy': 'false'}
        )

        assert len(agents) == 1
        assert agents[0]['hostname'] == 'staging-web-01'

        agents = get_latest_agents(
            query_params={'healthy': 'true'}
        )
        assert len(agents) == 3

        hostnames = {agent['hostname'] for agent in agents}
        assert hostnames == {'web-server-01', 'db-server-01', 'offline-server'}

    def test_filter_ignores_invalid_healthy_value(self):
        """
        Tests that an invalid value for the 'healthy' filter is ignored.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'healthy': 'maybe'}
        )

        assert len(agents) == 4

    def test_filter_by_online_offline_status(self):
        """
        Tests filtering by 'online'/'offline' status.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'status': 'offline'}
        )
        assert len(agents) == 1
        assert agents[0]['hostname'] == 'offline-server'

        agents = get_latest_agents(
            query_params={'status': 'online'}
        )
        assert len(agents) == 3

        hostnames = {agent['hostname'] for agent in agents}
        assert hostnames == {'web-server-01', 'db-server-01', 'staging-web-01'}

    def test_filter_ignores_invalid_status_value(self):
        """
        Tests that an invalid value for the 'status' filter is ignored.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'status': 'dead'}
        )

        assert len(agents) == 4

    def test_combined_filters_work_together(self):
        """
        Tests a combination of multiple different filters.
        """
        self.setup_filtering_data()
        params = {
            'tag_env': 'production',
            'healthy': 'true',
            'status': 'online'
        }
        agents = get_latest_agents(query_params=params)

        assert len(agents) == 2

        hostnames = {agent['hostname'] for agent in agents}
        assert hostnames == {'web-server-01', 'db-server-01'}

    def test_filter_strips_whitespace_from_values(self):
        """
        Tests that leading/trailing whitespace is ignored in filter values.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'tag_role': '  web  '}
        )

        assert len(agents) == 2

        hostnames = {agent['hostname'] for agent in agents}
        assert hostnames == {'web-server-01', 'staging-web-01'}

    def test_filter_returns_no_results_for_nonexistent_match(self):
        """
        Tests that a query with no possible match returns an empty list.
        """
        self.setup_filtering_data()
        agents = get_latest_agents(
            query_params={'hostname': 'nonexistent-host'}
        )

        assert len(agents) == 0
        assert agents == []
