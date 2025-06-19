import logging
import os
import tempfile

import mock
import pytest

from agents.utils.logtools import LOG_CONFIG_PATH


def _setup_fallback_file_logger(name, file, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.FileHandler(file)
    logger.addHandler(handler)

    return logger


@pytest.yield_fixture
def mock_supervisor():
    from agents.supervisor import AgentSupervisor

    agent = mock.MagicMock()
    agent.server_name = 'mock-server'

    supervisor = AgentSupervisor(agent)

    tmp = tempfile.NamedTemporaryFile(delete=False)

    try:
        logging.config.fileConfig(
            LOG_CONFIG_PATH,
            defaults={
                'agent_name': agent.server_name, 'log_path': tmp.name
            },
        )
    except Exception:
        logger = _setup_fallback_file_logger(
            name='-'.join([agent.server_name, 'supervisor']),
            file=tmp.name,
        )
        supervisor.logger = logger

    setattr(supervisor, 'logfile', tmp)

    yield supervisor

    tmp.close()
    os.remove(tmp.name)


@pytest.mark.coro
def test_unit_start_event_loop_with_no_tasks_logged(
    mock_supervisor, monkeypatch
):
    monkeypatch.setattr('coro.event_loop', lambda timeout: None)

    mock_supervisor.start()

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine queue is empty'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_sleep_negative_interval_logged(mock_supervisor):
    mock_supervisor.sleep(-1)

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Negative sleep interval not allowed'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_schedule_unschedule_coro_logged(mock_supervisor):
    """Test task scheduling and unscheduling with supervisor."""
    def mock_schedule_task(*args, **kwargs):
        pass

    idx = mock_supervisor.schedule(mock_schedule_task)
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
def test_schedule_weak_coro_logged(mock_supervisor):
    """Test proper scheduling of a 'weak' coro."""
    def mock_weak_task(*args, **kwargs):
        pass

    idx = mock_supervisor.schedule(mock_weak_task, weak=True)
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
def test_unschedule_nonexistent_coro_logged(mock_supervisor):
    """
    Test proper handling and logging of trying to unschedule nonexistent
    coro.
    """
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
def test_double_unschedule_coro_logged(mock_supervisor):
    """
    Test proper handling and logging of trying to unschedule the same
    coro twice.
    """
    def mock_unschedule_task(*args, **kwargs):
        pass

    idx = mock_supervisor.schedule(mock_unschedule_task)
    assert mock_supervisor.get_coro(idx) is not None

    mock_supervisor.unschedule(idx)
    assert mock_supervisor.get_coro(idx, log=False) is None

    mock_supervisor.unschedule(idx)
    assert mock_supervisor.get_coro(idx, log=True) is None, (
        'Unexpected coroutine found in the scheduler'
    )

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
def test_exit_task_scheduled(mock_supervisor):
    mock_supervisor.schedule_exit()

    assert mock_supervisor.has_coros(count_exit_coro=True), (
        'Failed to schedule exit task'
    )


@pytest.mark.coro
def test_exit_task_scheduled_twice_logged(mock_supervisor):
    mock_supervisor.schedule_exit()
    mock_supervisor.schedule_exit()

    assert mock_supervisor.has_coros(count_exit_coro=True), (
        'Failed to schedule exit task'
    )

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = (
        'Exit coroutine is already in task - only one at a time is permitted'
    )

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )
