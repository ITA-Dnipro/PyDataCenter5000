import logging
import os
import tempfile

import mock
import pytest

from agents.utils import make_callback


@pytest.mark.coro
@pytest.mark.integration
def test_integration_start_event_loop_with_no_tasks_logged(mock_supervisor):
    """
    Test that starting the event queue with only the exit coro scheduled
    is handled and logged properly.
    """
    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine queue is empty'

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

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
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
def test_jitter_backoff_delays(mock_supervisor, monkeypatch):
    """
    Test that uncorrelated jitter backoff delays are consumed as expected
    by the supervisor.
    """
    def mock_fail_task(*args, **kwargs):
        raise RuntimeError('I always fail')

    def mock_jitter(min_delay, max_delay):
        for delay in [0.2, 0.3]:
            yield delay

    monkeypatch.setattr('agents.supervisor.jitter', mock_jitter)

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

    assert len(intervals) == 2

    for interval, target in zip(intervals, [0.2, 0.3]):
        assert abs(interval - target) < 1e-6


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

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
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
def test_task_with_timeout_callback_logged(mock_supervisor, monkeypatch):
    """Test that timeout callback is properly called and logged."""
    def mock_timeout_task(*args, **kwargs):
        import coro
        coro.sleep_relative(10)

    flag = {'on_timeout_calls': 0}

    def mock_on_timeout(idx, retry):
        flag['on_timeout_calls'] += 1

    mock_on_timeout_callback = make_callback(mock_on_timeout)

    idx = mock_supervisor.schedule(
        mock_timeout_task,
        max_retries=1,
        timeout=0.1,
        on_timeout=mock_on_timeout_callback,
    )
    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Task %d executing timeout callback' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )

    assert flag['on_timeout_calls'] == 1, (
        'Unexpected value %d of on_timeout_calls' % flag['on_timeout_calls']
    )


@pytest.mark.coro
@pytest.mark.integration
def test_task_with_retry_callback_logged(mock_supervisor, monkeypatch):
    """Test that retry callback is properly called and logged."""
    def mock_failed_task(*args, **kwargs):
        raise RuntimeError('I always fail')

    flag = {'on_retry_calls': 0}

    def mock_on_retry(idx, retry):
        flag['on_retry_calls'] += 1

    mock_on_retry_callback = make_callback(mock_on_retry)

    idx = mock_supervisor.schedule(
        mock_failed_task,
        max_retries=2,
        min_delay=0.1,
        max_delay=0.5,
        on_retry=mock_on_retry_callback,
    )
    mock_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Task %d executing retry callback' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )

    assert flag['on_retry_calls'] == 1, (
        'Unexpected value %d of on_retry_calls' % flag['on_retry_calls']
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

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
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


@pytest.mark.coro
@pytest.mark.integration
def test_exit_task_should_exit_logged(mock_supervisor):
    """Test that custom should_exit callable works as expected."""
    flags = {'should_exit': False}

    def mock_dummy_task(*args, **kwargs):
        flags['should_exit'] = True

    mock_supervisor.schedule(mock_dummy_task, min_delay=0.1, max_delay=0.5)
    mock_supervisor.schedule_exit(
        min_delay=0.1, max_delay=0.5, should_exit=lambda: flags['should_exit']
    )

    with pytest.raises(SystemExit):
        mock_supervisor.start()

    with open(mock_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Event loop exiting...'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )
