import logging
import random
import threading

import coro

from .utils.logtools import maybe_log_message


def jitter(base, cap):
    """
    Generator for decorralated jitter backoff.

    Parameters:
        base (int | float): Minimum delay (in seconds).
        cap (int | float): Maximum delay (in seconds).
    """
    interval = base

    while True:
        interval = min(cap, random.uniform(base, interval * 3))
        yield interval


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

        self._coros = {}  # Store coroutine IDs and references
        self._lock = threading.Lock()

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent.server_name, 'supervisor'])
        )

    def start(self, timeout=30):
        """Starts the event loop. Blocks until excplicitly stopped."""
        if not self._coros:
            maybe_log_message(
                'Coroutine queue is empty',
                logger=self.logger,
                level=logging.WARNING,
            )

        coro.event_loop(timeout)

    def sleep(self, interval):
        """
        Sleep and yield to event loop for a duration of the interval.

        interval (int): Sleep interval duration (in seconds).
        """
        if interval < 0:
            maybe_log_message(
                'Negative sleep interval not allowed', logger=self.logger
            )
            return

        coro.sleep_relative(interval)

    def put_coro(self, idx, coroutine):
        with self._lock:
            self._coros[idx] = coroutine

    def get_coro(self, idx):
        with self._lock:
            if idx not in self._coros:
                maybe_log_message(
                    'Coroutine %d not in tasks' % idx,
                    logger=self.logger,
                    level=logging.WARNING,
                )
                return

            return self._coros[idx]

    @property
    def last_coro(self):
        with self._lock:
            return max(self._coros.keys()) if self._coros else 0

    def schedule(
        self,
        task,
        max_retries=3,
        min_delay=2,
        max_delay=10,
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
            backoff = jitter(min_delay, max_delay)

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
                            'Task %d failed on retry %d due to error: %s' % (
                                idx, retry, str(e)
                            ),
                            logger=self.logger,
                        )
                    else:
                        maybe_log_message(
                            (
                                'Task %d finished successfully after %d '
                                'retry(-ies)' % (idx, retry)
                            ),
                            logger=self.logger,
                            level=logging.INFO,
                        )

                        return

                    if retry != max_retries:
                        delay = next(backoff)

                        maybe_log_message(
                            'Coroutine %d sleeping for %d s' % (idx, delay),
                            logger=self.logger,
                            level=logging.DEBUG,
                        )

                        self.sleep(delay)
                else:
                    maybe_log_message(
                        (
                            'Task %d could not complete after %d retry(-ies)'
                            % (idx, max_retries)
                        ),
                        logger=self.logger,
                        level=logging.WARNING,
                    )

                    return
            finally:
                if not weak:
                    self.unschedule(idx)

        coroutine = coro.spawn(run_task)
        if not weak:
            self.put_coro(idx, coroutine)

        return idx

    def unschedule(self, idx):
        """
        Unscedule task, i.e., remove it from the list of tracked
        coroutines.

        Parameters:
            idx (int): Index of coroutine to unschedule.
        """
        with self._lock:
            self._coros.pop(idx, None)

    def schedule_exit(self, min_delay=2, max_delay=30):
        """
        Schedule a periodic check for whether all of the tracked tasks
        have finished. Once the task queue is empty, the event loop will
        be stopped via SystemExit.

        Parameters:
            interval (int, optional): Time (in seconds) between stopping
                condition checks. Default is 30.
        """
        def exit():
            backoff = jitter(min_delay, max_delay)

            while True:
                with self._lock:
                    if not self._coros:
                        break

                delay = next(backoff)

                maybe_log_message(
                    'Exit coroutine sleeping for %d s' % delay,
                    logger=self.logger,
                    level=logging.DEBUG,
                )

                self.sleep(delay)

            maybe_log_message(
                'Event loop exiting...',
                logger=self.logger,
                level=logging.INFO,
            )

            coro.set_exit()

        coro.spawn(exit)
