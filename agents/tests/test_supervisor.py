import logging
import os
import tempfile

import pytest
from mock import MagicMock

from agents.utils.logtools import LOG_CONFIG_PATH


@pytest.yield_fixture
def mock_supervisor():
    from agents.supervisor import AgentSupervisor

    agent = MagicMock()
    agent.server_name = 'mock-server'

    supervisor = AgentSupervisor(agent)

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
    assert mock_supervisor.get_coro(idx) is not None

    mock_supervisor.unschedule(idx)
    assert mock_supervisor.get_coro(idx, log=True) is None

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine %d not in tasks' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_schedule_weak_coro(mock_supervisor):
    """Test proper scheduling of a 'weak' coro."""
    def mock_task(*args, **kwargs):
        pass

    idx = mock_supervisor.schedule(mock_task, weak=True)
    assert mock_supervisor.get_coro(idx, log=True) is None

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine %d not in tasks' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_unschedule_nonexistent_coro(mock_supervisor):
    """
    Test proper handling and logging of trying to unschedule nonexistent
    coro.
    """
    def mock_task(*args, **kwargs):
        pass

    assert mock_supervisor.get_coro(-1) is None, (
        'Unexpected coroutine found in the scheduler'
    )

    mock_supervisor.unschedule(-1)

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine -1 not in tasks'

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
        mock_supervisor.schedule(mock_task, max_retries=1, num=n + 1)

    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    assert all(flags.values()), 'Not all scheduled tasks have run'

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    for n in range(ntasks):
        msg = 'Task %d finished successfully after 1 retry(-ies)' % (n + 1)

        assert msg in contents, (
            'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
        )


@pytest.mark.coro
@pytest.mark.integration
def test_task_timeout(mock_supervisor):
    """Test proper handling and logging of task timeout."""
    def mock_task(*args, **kwargs):
        import coro
        coro.sleep_relative(10)

    idx = mock_supervisor.schedule(
        mock_task,
        max_retries=1,
        timeout=0.1,
    )
    mock_supervisor.schedule_exit(interval=0.1)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    assert not mock_supervisor.has_coros(), (
        'Unexpected supervisor status: coro queue is not empty'
    )

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Task %d timed out' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
@pytest.mark.integration
def test_task_error(mock_supervisor):
    """Test proper handling and logging of task error."""
    def mock_task(*args, **kwargs):
        raise RuntimeError('Task failed for some reason')

    idx = mock_supervisor.schedule(mock_task, max_retries=1)
    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    assert not mock_supervisor.has_coros(), (
        'Unexpected supervisor status: coro queue is not empty'
    )

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = (
        'Task %d failed on retry 1 due to error: Task failed for some reason'
        % idx
    )

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )
