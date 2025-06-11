import logging

import coro

from .utils.logtools import FALLBACK_LOGGER, maybe_log_message


class AgentSupervisor(object):
    """Supervisor that monitors and manages agent coroutines."""

    def __init__(self, agent):
        self.agent = agent
        self.running = False

        self._tasks = []

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent.server_name, 'supervisor'])
        )

    def start(self):
        """Starts the event loop. Blocks until excplicitly stopped."""
        coro.event_loop()

    def schedule(self, task, interval=30, *args, **kwargs):
        """
        Schedule a periodic coroutine task.

        Parameters:
            task (Callable): Function-like to execute periodically.
            interval (int, optional): Time (in seconds) between task
                executions. Default is 30.
            *args: Positional arguments passed to task's callable.
            **kwargs: Keyword arguments passed to task's callable.
        """
        if not self.running:
            self.running = True

        def run_task(*args, **kwargs):
            while self.running:
                try:
                    task(*args, **kwargs)
                except Exception as e:
                    maybe_log_message(
                        'Scheduled task failed due to error: %s' % str(e),
                        logger=self.logger,
                        fallback_logger=FALLBACK_LOGGER,
                    )

                coro.sleep_relative(interval)

        coroutine = coro.spawn(run_task, *args, **kwargs)
        self._tasks.append(coroutine)

        return coroutine

    def schedule_exit(
        self, stop_condition, interval=30, prestop=None, *args, **kwargs
    ):
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
            if stop_condition():
                if prestop is not None:
                    prestop(*args, **kwargs)

                self.running = False

                coro.set_exit()

        return self.schedule(exit, interval=interval)
