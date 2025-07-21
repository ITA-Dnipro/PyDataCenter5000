import logging

from agents_infra.tasks.basetask import BaseTask
from agents_infra.utils.auth import Authentication
from agents_infra.utils.logtools import maybe_log_message


class FetchCommandTask(BaseTask):

    def handle(self):
        data = self.agent.fetch_command_from_controller(
            api_key=Authentication.get_key()
        )
        if data:
            maybe_log_message(
                'Fetched command from controller: %s' % data,
                logger=self.agent.logger,
                level=logging.INFO
            )
            self.agent.maybe_add_command_to_queue(data)
        else:
            maybe_log_message(
                'No command fetched from controller.',
                logger=self.agent.logger,
                level=logging.DEBUG
            )


class ExecuteCommandTask(BaseTask):
    DEFAULT_TIMEOUT = 60

    def handle(self):
        if self.supervisor:
            self.supervisor.schedule(
                self.agent.execute_command, timeout=self.DEFAULT_TIMEOUT
            )
