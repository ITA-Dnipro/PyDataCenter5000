import json
import logging
import urllib

from agents_infra.tasks.base_http_task import NOT_FETCHED_YET, BaseGetTask
from agents_infra.utils.logtools import maybe_log_message

DEFAULT_TIMEOUT = 60


def _build_url_with_params(base_url, params):
    if not params:
        return base_url
    return base_url + '?' + urllib.urlencode(params)


class FetchAndHandleCommandTask(BaseGetTask):

    def __init__(self, agent, endpoint, interval, supervisor):
        endpoint = _build_url_with_params(
            endpoint, {'hostname': agent.hostname}
        )
        super(FetchAndHandleCommandTask,
              self).__init__(agent, endpoint, interval)
        self.supervisor = supervisor

    def _handle_fetched_data(self):
        if self.data is NOT_FETCHED_YET:
            maybe_log_message(
                'Data not fetched yet - skipping processing.',
                logger=self.agent.logger,
                level=logging.WARNING
            )
            return

        if self.data:
            maybe_log_message(
                'Fetched command from controller: %r' % self.data,
                logger=self.agent.logger,
                level=logging.INFO
            )
            command_dict = json.loads(self.data)
            self.agent.maybe_add_command_to_queue(command_dict)
            self.supervisor.schedule(
                self.agent.execute_command, timeout=DEFAULT_TIMEOUT
            )
        else:
            maybe_log_message(
                'No command fetched from controller.',
                logger=self.agent.logger,
                level=logging.DEBUG
            )
