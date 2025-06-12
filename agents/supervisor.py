import logging

import coro

from .utils.logtools import FALLBACK_LOGGER, maybe_log_message


class AgentSupervisor(object):
    """Supervisor that monitors and manages agent coroutines."""

    def __init__(self, agent):
        self.agent = agent

        self.coros = {}  # Store coroutine IDs and references

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent.server_name, 'supervisor'])
        )

    @property
    def last_coro(self):
        return max(self.coros.keys()) if self.coros else 0

    def start(self):
        """Starts the event loop. Blocks until excplicitly stopped."""
        try:
            coro.event_loop()
        except KeyboardInterrupt:
            maybe_log_message(
                'Interrupted: exiting event loop...',
                logger=self.logger,
                fallback_logger=FALLBACK_LOGGER,
                level=logging.INFO,
            )

            coro.set_exit()

    def sleep(self, interval):
        """Yield to event loop for a duration of the interval."""
        coro.sleep_relative(interval)

    def schedule(
        self, task, max_retries=3, interval=5, idx=None, *args, **kwargs
    ):
        """
        Schedule a periodic coroutine task.

        Parameters:
            task (Callable): Function-like to execute periodically.
            interval (int, optional): Time (in seconds) between task
                executions. Default is 30.
            *args: Positional arguments passed to task's callable.
            **kwargs: Keyword arguments passed to task's callable.
        """
        if idx is None:
            idx = self.last_coro + 1

        def run_task():
            for _ in range(max_retries):
                try:
                    task(*args, **kwargs)
                except Exception as e:
                    maybe_log_message(
                        'Scheduled task failed due to error: %s' % str(e),
                        logger=self.logger,
                        fallback_logger=FALLBACK_LOGGER,
                    )

                self.sleep(interval)
            else:
                maybe_log_message(
                    'Task %d finished' % idx,
                    logger=self.logger,
                    fallback_logger=FALLBACK_LOGGER,
                )

                self.unschedule(idx)

        coroutine = coro.spawn(run_task)
        self.coros[idx] = coroutine

        return idx

    def unschedule(self, idx):
        if idx not in self.coros:
            maybe_log_message(
                'Coroutine %d not in tasks' % idx,
                logger=self.logger,
                fallback_logger=FALLBACK_LOGGER,
            )

        self.coros.pop(idx)

    def schedule_exit(self, interval=1, prestop=None, *args, **kwargs):
        """
        Schedule a periodic check for a stopping condition. When the
        condition is met, optionally run a prestop callable and exit.

        Parameters:
            stop_condition (Callable): Function-like returning True if
                the event loop should be stopped.
            interval (int, optional): Time (in seconds) between stopping
                condition checks. Default is 30.
            prestop (Callable, optional): Function-like to call before
                stopping the event loop. Default is None.
            *args: Positional arguments passed to prestop callable.
            **kwargs: Keyword arguments passed to prestop callable.
        """
        def exit():
            while any(idx != 0 for idx in self.coros):
                self.sleep(interval)
            else:
                if prestop is not None:
                    prestop(*args, **kwargs)

                coro.set_exit()

        return self.schedule(exit, max_retries=1, interval=interval, idx=0)
