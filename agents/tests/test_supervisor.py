import pytest
from mock import MagicMock


@pytest.mark.coro
class TestAgentSupervisor(object):
    @classmethod
    def setup_class(cls):
        cls.agent = MagicMock()
        cls.agent.server_name = 'mock-server'

        cls.supervisor = __import__(
            'agents.supervisor', fromlist=['AgentSupervisor']
        ).AgentSupervisor(cls.agent)

    def test_schedule_unschedule_coro(self):
        def mock_task(*args, **kwargs):
            pass

        idx = self.supervisor.schedule(mock_task, max_retries=3, interval=1)
        assert idx in self.supervisor.coros

        self.supervisor.unschedule(idx)
        assert idx not in self.supervisor.coros
