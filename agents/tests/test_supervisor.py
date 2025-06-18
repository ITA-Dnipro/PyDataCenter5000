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
@pytest.mark.integration
def test_task_execution_logged(mock_supervisor):
    """Test coroutine execution in the event loop."""
    ntasks = 2

    idxs, flags = [], {}

    def mock_execution_task(*args, **kwargs):
        flags['task ran'] = True

    for n in range(ntasks):
        flags['task ran'] = False

        # Schedule mock_task ntask times
        idxs.append(
            mock_supervisor.schedule(mock_execution_task, max_retries=1)
        )

    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    assert all(flags.values()), 'Not all scheduled tasks have run'

    with open(mock_supervisor.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    for idx in idxs:
        msg = 'Task %d finished successfully after 1 retry(-ies)' % idx

        assert msg in contents, (
            'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
        )


@pytest.mark.coro
@pytest.mark.integration
def test_jitter_backoff_logged(mock_supervisor, monkeypatch):
    def mock_fail_task(*args, **kwargs):
        raise RuntimeError('I always fail')

    def mock_jitter(min_delay, max_delay):
        for delay in [0.2, 0.3, 0.4]:
            yield delay

    monkeypatch.setattr('utils.jitter', mock_jitter)

    mock_supervisor.schedule(mock_fail_task, max_retries=3)
    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    intervals = []

    with mock.patch.object(
        mock_supervisor,
        'sleep',
        side_effect=lambda interval: intervals.append(interval),
    ):
        with pytest.raises(SystemExit):
            mock_supervisor.start()

    assert len(intervals) == 3


@pytest.mark.coro
@pytest.mark.integration
def test_task_timeout_logged(mock_supervisor):
    """Test proper handling and logging of task timeout."""
    def mock_timeout_task(*args, **kwargs):
        import coro
        coro.sleep_relative(10)

    idx = mock_supervisor.schedule(
        mock_timeout_task,
        max_retries=1,
        timeout=0.1,
    )
    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

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
def test_task_error_logged(mock_supervisor):
    """Test proper handling and logging of task error."""
    def mock_error_task(*args, **kwargs):
        raise RuntimeError('Task failed for some reason')

    idx = mock_supervisor.schedule(mock_error_task, max_retries=1)
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
