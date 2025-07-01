import pytest


@pytest.mark.coro
def test_unit_start_event_loop_with_no_tasks_logged(
    monkeypatch,
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    monkeypatch.setattr('coro.event_loop', lambda timeout: None)

    dummy_supervisor.start()

    assert_msg_in_logfile('Coroutine queue is empty')


@pytest.mark.coro
def test_sleep_negative_interval_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    dummy_supervisor.sleep(-1)
    assert_msg_in_logfile('Negative sleep interval not allowed')


@pytest.mark.coro
def test_schedule_unschedule_coro_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test task scheduling and unscheduling with supervisor."""
    def mock_schedule_task(*args, **kwargs):
        pass

    idx = dummy_supervisor.schedule(mock_schedule_task)
    assert dummy_supervisor.get_coro(idx) is not None

    dummy_supervisor.unschedule(idx)
    assert dummy_supervisor.get_coro(idx, log=True) is None

    assert_msg_in_logfile('Coroutine %d not in tasks' % idx)


@pytest.mark.coro
def test_schedule_weak_coro_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """Test proper scheduling of a 'weak' coro."""
    def mock_weak_task(*args, **kwargs):
        pass

    idx = dummy_supervisor.schedule(mock_weak_task, weak=True)
    assert dummy_supervisor.get_coro(idx, log=True) is None

    assert_msg_in_logfile('Coroutine %d not in tasks' % idx)


@pytest.mark.coro
def test_unschedule_nonexistent_coro_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """
    Test proper handling and logging of trying to unschedule nonexistent
    coro.
    """
    assert dummy_supervisor.get_coro(-1) is None, (
        'Unexpected coroutine found in the scheduler'
    )

    dummy_supervisor.unschedule(-1)

    assert_msg_in_logfile('Coroutine -1 not in tasks')


@pytest.mark.coro
def test_double_unschedule_coro_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    """
    Test proper handling and logging of trying to unschedule the same
    coro twice.
    """
    def mock_unschedule_task(*args, **kwargs):
        pass

    idx = dummy_supervisor.schedule(mock_unschedule_task)
    assert dummy_supervisor.get_coro(idx) is not None

    dummy_supervisor.unschedule(idx)
    assert dummy_supervisor.get_coro(idx, log=False) is None

    dummy_supervisor.unschedule(idx)
    assert dummy_supervisor.get_coro(idx, log=True) is None, (
        'Unexpected coroutine found in the scheduler'
    )

    assert_msg_in_logfile('Coroutine %d not in tasks' % idx)


@pytest.mark.coro
def test_exit_task_scheduled(dummy_supervisor):
    dummy_supervisor.schedule_exit()

    assert dummy_supervisor.has_coros(count_exit_coro=True), (
        'Failed to schedule exit task'
    )


@pytest.mark.coro
def test_exit_task_scheduled_twice_logged(
    dummy_supervisor,
    setup_temp_file_logging_with_fallback,
    assert_msg_in_logfile
):
    dummy_supervisor.schedule_exit()
    dummy_supervisor.schedule_exit()

    assert dummy_supervisor.has_coros(count_exit_coro=True), (
        'Failed to schedule exit task'
    )

    assert_msg_in_logfile(
        'Exit coroutine is already in task - only one at a time is permitted'
    )
