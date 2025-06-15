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
        weak=False,
        *args,
        **kwargs
    ):
        """
        Schedule a periodic coroutine task.

        Parameters:
            task (Callable): Function-like to execute periodically.
            max_retries (int, optional): Maximum number of retries on
                failure. Default is 3.
            interval (int, optional): Time (in seconds) between retries.
                Default is 5.
            timeout (int, optional): Timeout for task run. Task is
                considered timed out if it didn't execute in the
                allocated time. Default is None.
            weak (bool, optional): 'Weak' rask will not be tracked by the
                supervisor, i.e., the event loop can be stopped regardless
                of whether the task has finished. Default is False.
            *args: Positional arguments passed to task's callable.
            **kwargs: Keyword arguments passed to task's callable.
        """
        idx = self.last_coro + 1

        def run_task():
            try:
                for retry in range(1, max_retries + 1):
                    try:
                        if timeout:
                            coro.with_timeout(timeout, task, *args, **kwargs)
                        else:
                            task(*args, **kwargs)
                    except coro.TimeoutError:
                        maybe_log_message(
                            'Task %d timed out' % idx, logger=self.logger
                        )
                    except Exception as e:
                        maybe_log_message(
                            'Task %d failed due to error: %s' % (idx, str(e)),
                            logger=self.logger,
                        )
                    else:
                        maybe_log_message(
                            'Task %d finished successfully' % idx,
                            logger=self.logger,
                            level=logging.INFO,
                        )

                        return

                    if retry != max_retries:
                        self.sleep(interval)
                else:
                    maybe_log_message(
                        'Task %d could not complete' % idx,
                        logger=self.logger,
                        level=logging.WARNING,
                    )

                    return
            finally:
                if not weak:
                    self.unschedule(idx)

        coroutine = coro.spawn(run_task)
        if not weak:
            self.coros[idx] = coroutine

        return idx

    def unschedule(self, idx):
        """
        Unscedule task, i.e., remove it from the list of tracked
        coroutines.

        Parameters:
            idx (int): Index of coroutine to unschedule.
        """
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
        Schedule a periodic check for whether all of the tracked tasks
        have finished. Once the task queue is empty, the event loop will
        be stopped via SystemExit.

        Parameters:
            interval (int, optional): Time (in seconds) between stopping
                condition checks. Default is 30.
        """
        def exit():
            while self.coros:
                self.sleep(interval)
            else:
                coro.set_exit()

        return self.schedule(exit, max_retries=1, interval=interval, weak=True)
