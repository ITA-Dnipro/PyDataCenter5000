import itertools
import logging
import threading

import coro

from .utils import jitter, maybe_log_message


class AgentSupervisor(object):
    """
    Supervisor that monitors and manages agent coroutines.

    Attributes:
        agent (ServerAgent): Agent instance under supervision.

    Methods:
        start(): Start the event loop and block until explicitly stopped.
        sleep(interval): Yield to event loop and sleep for a duration of
            the interval.
        schedule(task, ...): Schedule a periodic coroutine task.
        unschedule(idx): Unschedule a coroutine by ID.
        schedule_exit(...): Schedule a periodic coroutine to monitor for
            exit.
    """

    def __init__(self, agent, managers=None):
        self.agent = agent
        self.managers = managers or []

        self._coros = {}  # Store coroutine IDs and references
        self._lock = threading.Lock()

        self.counter = itertools.count(1)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent.server_name, 'supervisor'])
        )

    def start(self, timeout=30):
        """Starts the event loop. Blocks until explicitly stopped."""
        if not self.has_coros(count_exit_coro=False):
            maybe_log_message(
                'Coroutine queue is empty',
                logger=self.logger,
                level=logging.WARNING,
            )

        coro.event_loop(timeout)

    def start_managers(self):
        """Starts the managers. Blocks until explicitly stopped."""
        for manager in self.managers:
            manager.start()
        self.logger.info('All managers started. Running main loop...')
        signal.pause()

    def stop_managers(self):
        """Stops the managers."""
        for manager in self.managers:
            manager.stop()

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

    def has_coros(self, count_exit_coro=False):
        """
        Check if task dict is empty.

        Parameters:
            count_exit_coro (bool, optional): Whether to count the exit
                task. Default is False.

        Returns:
            bool: Whether task dict is not empty.
        """
        if count_exit_coro:
            with self._lock:
                return bool(self._coros)

        with self._lock:
            return any(idx != 0 for idx in self._coros)

    def put_coro(self, idx, coroutine):
        """
        Add coroutine to the task dict.

        Parameters:
            idx (int): Coroutine index.
            coroutine (coro): Coroutine instance.
        """
        with self._lock:
            self._coros[idx] = coroutine

    def get_coro(self, idx, log=True):
        """
        Get coroutine from the task dict by index.

        Parameters:
            log (bool, optional): Whether to log warning if coroutine
                not found. Default is True.

        Returns:
            coro: Coroutine instance.
        """
        with self._lock:
            if idx not in self._coros:
                if log:
                    maybe_log_message(
                        'Coroutine %d not in tasks' % idx,
                        logger=self.logger,
                        level=logging.WARNING,
                    )
                return

            return self._coros[idx]

    def schedule(
        self,
        task,
        on_success=None,
        max_retries=3,
        min_delay=2,
        max_delay=10,
        on_retry=None,
        timeout=None,
        on_timeout=None,
        weak=False,
        *args,
        **kwargs
    ):
        """
        Schedule a periodic coroutine task.

        Parameters:
            task (Callable): Callable to execute periodically.
            max_retries (int, optional): Maximum number of retries on
                failure. Default is 3.
            min_delay (int, optional): Minimum delay between retries
                (in seconds). Default is 2.
            max_delay (int, optional): Maximum delay between retries
                (in seconds). Default is 10.
            on_retry (Callable, optional): Callback function executed
                before the next retry. Default is None.
            timeout (int, optional): Task timeout. Default is None.
            on_timeout (Callable, optional): Callback function executed
                on task timeout. Default is None.
            weak (bool, optional): 'Weak' task will not be tracked by the
                supervisor, i.e., the event loop can be stopped regardless
                of whether the task has finished. Default is False.
            *args: Positional arguments passed to task's callable.
            **kwargs: Keyword arguments passed to task's callable.

        Returns:
            int: Task ID.
        """
        with self._lock:
            idx = next(self.counter)

        def run_task():
            try:
                backoff = jitter(min_delay, max_delay)

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

                        if on_timeout:
                            maybe_log_message(
                                'Task %d executing timeout callback' % idx,
                                logger=self.logger,
                                level=logging.INFO,
                            )

                            try:
                                on_timeout(idx, retry)
                            except Exception as e:
                                maybe_log_message(
                                    'Timeout callback failed due to error: %s'
                                    % str(e),
                                    logger=self.logger,
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

                        if on_success:
                            maybe_log_message(
                                'Task %d executing success callback' % idx,
                                logger=self.logger,
                                level=logging.INFO,
                            )

                            try:
                                on_success(idx, task)
                            except Exception as e:
                                maybe_log_message(
                                    'Success callback failed due to error: %s'
                                    % str(e),
                                    logger=self.logger,
                                )

                        return

                    if retry != max_retries:
                        delay = next(backoff)

                        maybe_log_message(
                            'Coroutine %d sleeping for %d s' % (idx, delay),
                            logger=self.logger,
                            level=logging.DEBUG,
                        )

                        try:
                            self.sleep(delay)
                        except Exception as e:
                            maybe_log_message(
                                'Retry callback failed due to error: %s'
                                % str(e),
                                logger=self.logger,
                            )
                    else:
                        if on_retry:
                            maybe_log_message(
                                'Task %d executing retry callback' % idx,
                                logger=self.logger,
                                level=logging.INFO,
                            )

                            on_retry(idx, task)
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

    def schedule_exit(self, min_delay=2, max_delay=30, should_exit=None):
        """
        Schedule a periodic check for whether all of the tracked tasks
        have finished. Once the task queue is empty, the event loop will
        be stopped via SystemExit.
        Note that only one exit coroutine can be scheduled at a time. Exit
        coroutine is always assigned index 0.

        Parameters:
            min_delay (int, optional): Minimum delay (in seconds).
                Default is 2.
            max_delay (int, optional): Maximum delay (in seconds).
                Default is 30.
            should_exit (Callable, optional): Custom callable to determine
                whether the event loop should exit. If not provided, the
                event loop will exit once all other coroutines have been
                unscheduled.
        """
        if self.get_coro(0, log=False):
            maybe_log_message(
                (
                    'Exit coroutine is already in task - '
                    'only one at a time is permitted'
                ),
                logger=self.logger,
                level=logging.WARNING,
            )
            return

        if not should_exit:
            def should_exit():
                return not self.has_coros(count_exit_coro=False)

        def exit():
            backoff = jitter(min_delay, max_delay)

            while True:
                if should_exit():
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

        coroutine = coro.spawn(exit)
        self.put_coro(0, coroutine)

    def _signal_handler(self, signum, frame):
        maybe_log_message(
            'Received signal %s, shutting down...' % signum,
            logger=self.logger,
            level=logging.INFO
        )
        self.stop_health_server()
        sys.exit(0)
