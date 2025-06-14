import logging
import os
import tempfile
import time

import pytest
from mock import MagicMock

from agents.utils.logtools import LOG_CONFIG_PATH


@pytest.yield_fixture
def mock_supervisor():
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

    setattr(supervisor, 'logfile', tmp)

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


@pytest.mark.coro
def test_schedule_weak_coro(mock_supervisor):
    """Test proper scheduling of a 'weak' coro."""
    def mock_task(*args, **kwargs):
        pass

    idx = mock_supervisor.schedule(mock_task, weak=True)
    assert idx not in mock_supervisor.coros


@pytest.mark.coro
def test_unschedule_nonexistent_coro(mock_supervisor):
    """
    Test proper handling and logging of trying to unschedule nonexistent
    coro.
    """
    def mock_task(*args, **kwargs):
        pass

    assert 0 not in mock_supervisor.coros, (
        'Unexpected coroutine found in the scheduler'
    )

    mock_supervisor.unschedule(0)

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine 0 not in tasks'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
@pytest.mark.integration
def test_task_execution(mock_supervisor):
    """Test coroutine execution in the event loop."""
    ntasks = 2

    flags = {}

    def mock_task(num, *args, **kwargs):
        flags['task %d ran' % num] = True

    for n in range(ntasks):
        flags['task %d ran' % (n + 1)] = False

        # Schedule mock_task ntask times
        mock_supervisor.schedule(
            mock_task, max_retries=1, interval=1, num=n + 1
        )

    mock_supervisor.schedule_exit(interval=0.1)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    assert all(flags.values()), 'Not all scheduled tasks have run'

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    for n in range(ntasks):
        msg = 'Task %d finished' % (n + 1)

        assert msg in contents, (
            'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
        )


@pytest.mark.coro
@pytest.mark.integration
def test_task_timeout(mock_supervisor):
    """Test proper handling and logging of task timeout."""
    def mock_task(num, *args, **kwargs):
        time.sleep(1)

    idx = mock_supervisor.schedule(mock_task, max_retries=1, timeout=0.1)
    mock_supervisor.schedule_exit(interval=0.1)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Task %d timed out' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )
