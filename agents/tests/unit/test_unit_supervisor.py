import pytest


@pytest.mark.coro
def test_unit_start_event_loop_with_no_tasks_logged(
    dummy_supervisor, monkeypatch
):
    monkeypatch.setattr('coro.event_loop', lambda timeout: None)

    dummy_supervisor.start()

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine queue is empty'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_sleep_negative_interval_logged(dummy_supervisor):
    dummy_supervisor.sleep(-1)

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Negative sleep interval not allowed'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_schedule_unschedule_coro_logged(dummy_supervisor):
    """Test task scheduling and unscheduling with supervisor."""
    def mock_schedule_task(*args, **kwargs):
        pass

    idx = dummy_supervisor.schedule(mock_schedule_task)
    assert dummy_supervisor.get_coro(idx) is not None

    dummy_supervisor.unschedule(idx)
    assert dummy_supervisor.get_coro(idx, log=True) is None

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine %d not in tasks' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_schedule_weak_coro_logged(dummy_supervisor):
    """Test proper scheduling of a 'weak' coro."""
    def mock_weak_task(*args, **kwargs):
        pass

    idx = dummy_supervisor.schedule(mock_weak_task, weak=True)
    assert dummy_supervisor.get_coro(idx, log=True) is None

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine %d not in tasks' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_unschedule_nonexistent_coro_logged(dummy_supervisor):
    """
    Test proper handling and logging of trying to unschedule nonexistent
    coro.
    """
    assert dummy_supervisor.get_coro(-1) is None, (
        'Unexpected coroutine found in the scheduler'
    )

    dummy_supervisor.unschedule(-1)

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine -1 not in tasks'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_double_unschedule_coro_logged(dummy_supervisor):
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

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Coroutine %d not in tasks' % idx

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


@pytest.mark.coro
def test_exit_task_scheduled(dummy_supervisor):
    dummy_supervisor.schedule_exit()

    assert dummy_supervisor.has_coros(count_exit_coro=True), (
        'Failed to schedule exit task'
    )


@pytest.mark.coro
def test_exit_task_scheduled_twice_logged(dummy_supervisor):
    dummy_supervisor.schedule_exit()
    dummy_supervisor.schedule_exit()

    assert dummy_supervisor.has_coros(count_exit_coro=True), (
        'Failed to schedule exit task'
    )

    with open(dummy_supervisor.logger.handlers[0].baseFilename, 'r') as f:
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
