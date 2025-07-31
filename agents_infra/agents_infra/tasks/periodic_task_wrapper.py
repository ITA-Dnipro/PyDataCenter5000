def periodic_task_wrapper(task, interval, supervisor, *args, **kwargs):
    """
    Wraps a task for periodic scheduling with the supervisor.

    Args:
        task (callable): The task to run periodically.
            Should take no arguments.
        interval (int or float): The interval in seconds
            between task executions.
        supervisor (AgentSupervisor): The supervisor instance used to schedule
            and sleep coroutines.
        *args: Additional positional arguments passed to supervisor.schedule.
        **kwargs: Additional keyword arguments passed to supervisor.schedule.
            **WARNING**: The following parameters are ALWAYS overridden
            regardless of what is passed in **kwargs:
            - timeout: Set to 2 * interval for periodic tasks
            - max_retries: Set to 1 to avoid runaway scheduling on failure
            Any timeout or max_retries values in **kwargs will be ignored.

    Returns:
        callable: A coroutine function suitable
            for scheduling with supervisor.schedule.

    Notes:
        - This wrapper ensures that the task is rescheduled
            only after the interval, regardless of success or failure.
        - The wrapper yields to the event loop
            using supervisor.sleep(interval) after each run.
        - timeout and max_retries are hardcoded to prevent conflicts
            and ensure predictable behavior for periodic tasks.
    """

    def run():
        try:
            task()
        finally:
            supervisor.sleep(interval)
            supervisor.schedule(run,
                                timeout=2 * interval,
                                max_retries=1,
                                *args,
                                **kwargs)

    return run
