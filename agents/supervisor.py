import logging

import coro

from .utils.logtools import maybe_log_message


class AgentSupervisor(object):
    """
    Supervisor that monitors and manages agent coroutines.

    Attributes:
        agent (ServerAgent): Agent instance under supervision.
        coros (dict): Dictionary mapping coroutine IDs to coroutine
            references. ID 0 is reserved for exit coroutine.

    Methods:
        last_coro(): Get ID of the last scheduled coroutine.
        start(): Start the event loop and block until explicitly stopped.
        sleep(interval): Yield to event loop and sleep for a duration of
            the interval.
        schedule(task, max_retries, interval, idx, ...): Schedule a
            periodic coroutine task.
        unschedule(idx): Unschedule a coroutine by ID.
        schedule_exit(interval, prestop, ...): Schedule a periodic
            coroutine to monitor for exit.
    """

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

    def start(self, timeout=30):
        """Starts the event loop. Blocks until excplicitly stopped."""
        if not self.coros:
            maybe_log_message(
                'Coroutine queue is empty',
                logger=self.logger,
                level=logging.WARNING,
            )

        coro.event_loop(timeout)

    def sleep(self, interval):
        """Yield to event loop for a duration of the interval."""
        coro.sleep_relative(interval)

    def schedule(
        self,
        task,
        max_retries=3,
        interval=5,
        timeout=None,
        idx=None,
        *args,
        **kwargs
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
            try:
                for _ in range(max_retries):
                    try:
                        if timeout:
                            coro.with_timeout(timeout, task, *args, **kwargs)
                        else:
                            task(*args, **kwargs)
                    except coro.TimeoutError:
                        maybe_log_message('Task timed out', logger=self.logger)
                    except Exception as e:
                        maybe_log_message(
                            'Scheduled task failed due to error: %s' % str(e),
                            logger=self.logger,
                        )

                    self.sleep(interval)
                else:
                    maybe_log_message(
                        'Task %d finished' % idx,
                        logger=self.logger,
                        level=logging.INFO,
                    )
            finally:
                self.unschedule(idx)

        coroutine = coro.spawn(run_task)
        self.coros[idx] = coroutine

        return idx

    def unschedule(self, idx):
        if idx not in self.coros:
            maybe_log_message(
                'Coroutine %d not in tasks' % idx,
                logger=self.logger,
                level=logging.WARNING,
            )
            return

        self.coros.pop(idx)

    def schedule_exit(self, interval=30):
        """
        Schedule a periodic check for a stopping condition. When the
        condition is met, optionally run a prestop callable and exit.

        Parameters:
            interval (int, optional): Time (in seconds) between stopping
                condition checks. Default is 30.
        """
        def exit():
            while any(idx != 0 for idx in self.coros):
                for idx, co in self.coros.items():
                    if idx == 0:
                        continue

                    # Check for dead coroutines that may be stalling the
                    # exit - unschedule them if found.
                    if co.dead:
                        maybe_log_message(
                            'Coroutine %d is dead' % idx,
                            logger=self.logger,
                            level=logging.WARNING,
                        )

                        self.unschedule(idx)

                self.sleep(interval)
            else:
                return coro.set_exit()

        return self.schedule(exit, max_retries=1, interval=interval, idx=0)
