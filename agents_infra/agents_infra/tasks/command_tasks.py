import json
import logging
import urllib

from agents_infra.tasks.basetask import BaseTask
from agents_infra.utils.auth import Authentication
from agents_infra.utils.logtools import maybe_log_message


def _build_url_with_params(base_url, params):
    if not params:
        return base_url
    return base_url + '?' + urllib.urlencode(params)


class FetchCommandTask(BaseTask):

    def handle(self):
        url = _build_url_with_params(self.endpoint,
                                     {'hostname': self.agent.hostname})
        data = self.agent.get_data(
            url=url,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key(),
        )
        if data:
            maybe_log_message(
                'Fetched command from controller: %r' % data,
                logger=self.agent.logger,
                level=logging.INFO
            )
            command_dict = json.loads(data)
            self.agent.maybe_add_command_to_queue(command_dict)
        else:
            maybe_log_message(
                'No command fetched from controller.',
                logger=self.agent.logger,
                level=logging.DEBUG
            )


class ExecuteCommandTask(BaseTask):
    DEFAULT_TIMEOUT = 60

    def handle(self):
        self.supervisor.schedule(
            self.agent.execute_command, timeout=self.DEFAULT_TIMEOUT
        )
