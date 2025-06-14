import logging
import os
import tempfile

import pytest
from mock import MagicMock

from agents.utils.logtools import LOG_CONFIG_PATH


@pytest.yield_fixture(scope='session')
def mock_supervisor(monkeypatch):
    agent = MagicMock()
    agent.server_name = 'mock-server'

    supervisor = __import__(
        'agents.supervisor', fromlist=['AgentSupervisor']
    ).AgentSupervisor(agent)

    tmp = tempfile.NamedTemporaryFile(delete=False)

    logging.config.fileConfig(
        LOG_CONFIG_PATH,
        defaults={
            'agent_name': agent.server_name, 'log_path': tmp.name
        },
    )

    monkeypatch.setattr(supervisor, 'logfile', tmp)

    yield supervisor

    os.remove(tmp.name)


@pytest.mark.coro
def test_schedule_unschedule_coro(mock_supervisor):
    """Test task scheduling and unscheduling with supervisor."""
    def mock_task(*args, **kwargs):
        pass

    idx = mock_supervisor.schedule(mock_task)
    assert idx in mock_supervisor.coros

    mock_supervisor.unschedule(idx)
    assert idx not in mock_supervisor.coros


@pytest.mark.integration
def test_task_execution(mock_supervisor):
    """Test coroutine execution in the event loop."""
    flag = {'ran': False}

    def mock_task(*args, **kwargs):
        flag['ran'] = True

    mock_supervisor.schedule(mock_task, max_retries=1, interval=0)
    mock_supervisor.schedule_exit(interval=0.1)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    assert flag['ran']

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Task 1 finished'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )
