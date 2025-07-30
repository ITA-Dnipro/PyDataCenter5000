import abc

from agents_infra.utils.auth import Authentication

from .basetask import BaseTask

NOT_FETCHED_YET = object()
NOT_PRODUCED_YET = object()


class BaseHTTPTask(BaseTask):

    def __init__(self, agent, endpoint, interval):
        super(BaseHTTPTask, self).__init__(agent, interval)
        self.endpoint = endpoint


class BaseGetTask(BaseHTTPTask):

    def __init__(self, agent, endpoint, interval):
        super(BaseGetTask, self).__init__(agent, endpoint, interval)
        self.data = NOT_FETCHED_YET

    def _fetch(self):
        self.data = self.agent.get_data(
            url=self.endpoint,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key(),
        )
        return self.data

    def handle(self):
        self._fetch()
        return self._handle_fetched_data()

    @abc.abstractmethod
    def _handle_fetched_data(self):
        pass


class BasePostTask(BaseHTTPTask):

    def __init__(self, agent, endpoint, interval):
        super(BasePostTask, self).__init__(agent, endpoint, interval)
        self.payload = NOT_PRODUCED_YET

    def _post(self):
        return self.agent.post_data(
            url=self.endpoint,
            payload=self.payload,
            to_controller=True,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key(),
        )

    def handle(self):
        self._produce_payload()
        return self._post()

    @abc.abstractmethod
    def _produce_payload(self):
        pass
