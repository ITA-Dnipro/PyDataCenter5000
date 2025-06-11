import logging

import coro

from .utils.logtools import FALLBACK_LOGGER, maybe_log_message


class AgentSupervisor(object):

    def __init__(self, agent):
        self.agent = agent
        self.running = False

    @property
    def logger(self):
        return logging.getLogger(
            '-'.join([self.agent.server_name, 'supervisor'])
        )

    def start(self):
        coro.event_loop()

    def schedule(self, task, interval=30, *args, **kwargs):
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

        coro.spawn(run_task, *args, **kwargs)

    def schedule_exit(
        self, stop_condition, interval=30, prestop=None, *args, **kwargs
    ):
        def exit():
            if stop_condition():
                if prestop is not None:
                    prestop(*args, **kwargs)

                self.running = False

                coro.set_exit()

        self.schedule(exit, interval=interval)
