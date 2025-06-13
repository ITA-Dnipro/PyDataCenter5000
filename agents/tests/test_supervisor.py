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

        idx = self.supervisor.schedule(mock_task)
        assert idx in self.supervisor.coros

        self.supervisor.unschedule(idx)
        assert idx not in self.supervisor.coros

    @pytest.mark.integration
    def test_task_execution(self):
        flag = {'ran': False}

        def mock_task(*args, **kwargs):
            flag['ran'] = True

        self.supervisor.schedule(mock_task, max_retries=1, interval=0)
        self.supervisor.schedule_exit(interval=0.1)

        self.supervisor.start()

        assert flag['ran']
