from agents_infra.utils.sysinfo import generate_report

from .base_http_task import BasePostTask


class CollectAndSendStatusTask(BasePostTask):

    def _produce_payload(self):
        return self.agent.status_to_dict()


class CollectAndSendMetricsTask(BasePostTask):

    def __init__(self, agent, endpoint, interval):
        endpoint = endpoint + '?hostname=%s' % agent.hostname
        super(CollectAndSendMetricsTask,
              self).__init__(agent, endpoint, interval)

    def _produce_payload(self):
        report = generate_report(self.agent.logger)
        payload = {}
        for k in ('cpu', 'ram', 'disk', 'load_avg'):
            if k in report:
                payload[k] = report[k]
        return payload
