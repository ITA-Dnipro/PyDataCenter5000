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
            timestamp=self.right_now - timedelta(minutes=1)
        )
        self.newest_vm01 = ServerStatus.objects.create(
            hostname='vm-01',
            ip='192.168.0.1',
            uptime=200,
            healthy=False,
            timestamp=self.right_now
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
        newest_vm02 = ServerStatus.objects.create(
            hostname='vm-02',
            ip='192.168.0.2',
            uptime=300,
            healthy=True,
            timestamp=self.right_now
        )
        ServerStatus.objects.create(
            hostname='vm-02',
            ip='192.168.0.2',
            uptime=250,
            healthy=True,
            timestamp=self.right_now - timedelta(minutes=5)
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
