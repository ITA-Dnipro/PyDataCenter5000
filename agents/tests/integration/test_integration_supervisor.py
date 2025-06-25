import mock
import pytest

from agents.utils import make_callback


@pytest.mark.coro
@pytest.mark.integration
def test_integration_start_event_loop_with_no_tasks_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """
    Test that starting the event queue with only the exit coro scheduled
    is handled and logged properly.
    """
    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert_msg_in_logfile('Coroutine queue is empty')


@pytest.mark.coro
@pytest.mark.integration
def test_task_execution_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test coroutine execution in the event loop."""
    ntasks = 2

    idxs, flags = [], {}

    def mock_execution_task(idx, *args, **kwargs):
        flags['task %d ran' % idx] = True

    for n in range(1, ntasks + 1):
        flags['task %d ran' % n] = False

        # Schedule mock_task ntask times
        idx = dummy_supervisor.schedule(
            mock_execution_task, max_retries=1, idx=n
        )
        idxs.append(idx)

    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert all(flags.values()), 'Not all scheduled tasks have run'

    for idx in idxs:
        assert_msg_in_logfile(
            'Task %d finished successfully after 1 retry(-ies)' % idx
        )


@pytest.mark.coro
@pytest.mark.integration
def test_jitter_backoff_delays(
    monkeypatch,
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
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

    dummy_supervisor.schedule(mock_fail_task, max_retries=3)
    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    intervals = []

    with mock.patch.object(
        dummy_supervisor,
        'sleep',
        side_effect=lambda interval: intervals.append(interval),
    ):
        with pytest.raises(SystemExit):
            dummy_supervisor.start()

    assert len(intervals) == 2

    for interval, target in zip(intervals, [0.2, 0.3]):
        assert abs(interval - target) < 1e-6


@pytest.mark.coro
@pytest.mark.integration
def test_task_timeout_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test proper handling and logging of task timeout."""
    def mock_timeout_task(*args, **kwargs):
        import coro
        coro.sleep_relative(10)

    idx = dummy_supervisor.schedule(
        mock_timeout_task,
        max_retries=1,
        timeout=0.1,
    )
    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert not dummy_supervisor.has_coros(), (
        'Unexpected supervisor status: coro queue is not empty'
    )

    assert_msg_in_logfile('Task %d timed out' % idx)


@pytest.mark.coro
@pytest.mark.integration
def test_task_with_timeout_callback_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test that timeout callback is properly called and logged."""
    def mock_timeout_task(*args, **kwargs):
        import coro
        coro.sleep_relative(10)

    flag = {'on_timeout_calls': 0}

    def mock_on_timeout(idx, retry):
        flag['on_timeout_calls'] += 1

    mock_on_timeout_callback = make_callback(mock_on_timeout)

    idx = dummy_supervisor.schedule(
        mock_timeout_task,
        max_retries=1,
        timeout=0.1,
        on_timeout=mock_on_timeout_callback,
    )
    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert_msg_in_logfile('Task %d executing timeout callback' % idx)

    assert flag['on_timeout_calls'] == 1, (
        'Unexpected value %d of on_timeout_calls' % flag['on_timeout_calls']
    )


@pytest.mark.coro
@pytest.mark.integration
def test_task_with_retry_callback_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test that retry callback is properly called and logged."""
    def mock_failed_task(*args, **kwargs):
        raise RuntimeError('I always fail')

    flag = {'on_retry_calls': 0}

    def mock_on_retry(idx, retry):
        flag['on_retry_calls'] += 1

    mock_on_retry_callback = make_callback(mock_on_retry)

    idx = dummy_supervisor.schedule(
        mock_failed_task,
        max_retries=2,
        min_delay=0.1,
        max_delay=0.5,
        on_retry=mock_on_retry_callback,
    )
    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert_msg_in_logfile('Task %d executing retry callback' % idx)

    assert flag['on_retry_calls'] == 1, (
        'Unexpected value %d of on_retry_calls' % flag['on_retry_calls']
    )


@pytest.mark.coro
@pytest.mark.integration
def test_task_error_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test proper handling and logging of task error."""
    def mock_error_task(*args, **kwargs):
        raise RuntimeError('Task failed for some reason')

    idx = dummy_supervisor.schedule(mock_error_task, max_retries=1)
    dummy_supervisor.schedule_exit(min_delay=0.1, max_delay=0.5)

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert not dummy_supervisor.has_coros(), (
        'Unexpected supervisor status: coro queue is not empty'
    )

    assert_msg_in_logfile(
        'Task %d failed on retry 1 due to error: Task failed for some reason'
        % idx
    )


@pytest.mark.coro
@pytest.mark.integration
def test_exit_task_should_exit_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test that custom should_exit callable works as expected."""
    flags = {'should_exit': False}

    def mock_dummy_task(*args, **kwargs):
        flags['should_exit'] = True

    dummy_supervisor.schedule(mock_dummy_task, min_delay=0.1, max_delay=0.5)
    dummy_supervisor.schedule_exit(
        min_delay=0.1, max_delay=0.5, should_exit=lambda: flags['should_exit']
    )

    with pytest.raises(SystemExit):
        dummy_supervisor.start()

    assert_msg_in_logfile('Event loop exiting...')
