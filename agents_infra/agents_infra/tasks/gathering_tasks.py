from agents_infra.utils.auth import Authentication
from agents_infra.utils.sysinfo import generate_report

from .basetask import BaseTask


class CollectAndSendStatusTask(BaseTask):

    def handle(self):
        data = self.agent.status_to_dict()
        return self.agent.post_data(
            url=self.endpoint,
            payload=data,
            to_controller=True,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key()
        )


class CollectAndSendMetricsTask(BaseTask):

    def handle(self):
        report = generate_report(self.agent.logger)
        payload = {}
        for k in ('cpu', 'ram', 'disk', 'load_avg'):
            if k in report:
                payload[k] = report[k]
        return self.agent.post_data(
            url=self.endpoint + '?hostname=%s' % self.agent.hostname,
            payload=payload,
            to_controller=True,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key()
        )
