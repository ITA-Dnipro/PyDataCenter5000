from agents_infra.utils.auth import Authentication

from .basetask import BaseTask


class CollectAndSendStatusTask(BaseTask):

    def handle(self):
        data = self.agent.status_to_dict()
        self.agent.post_data(
            url=self.endpoint,
            payload=data,
            to_controller=True,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key()
        )


class CollectAndSendMetricsTask(BaseTask):

    def handle(self):
        report = self.agent.generate_report()
        payload = {}
        for k in ('cpu', 'ram', 'disk', 'load_avg'):
            if k in report:
                payload[k] = report[k]
        self.agent.post_data(
            url=self.endpoint + '?hostname=%s' % self.agent.hostname,
            payload=payload,
            to_controller=True,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key()
        )
