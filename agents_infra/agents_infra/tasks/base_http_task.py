import abc

from agents_infra.utils import Authentication
from agents_infra.utils.communication import AgentCommunication

from .basetask import BaseTask

# Sentinel objects that represent the state of the data
NOT_FETCHED_YET = object()
NOT_PRODUCED_YET = object()


class BaseHTTPTask(BaseTask):
    """
    Abstract base class for HTTP-based tasks.

    This class extends BaseTask to provide common functionality
    for tasks that interact with HTTP endpoints.
    """

    def __init__(self, agent, endpoint, interval):
        """
        Initialize the HTTP task.

        Args:
            agent (ServerAgent): The agent instance that owns this task
            endpoint (str): The HTTP endpoint URL for this task
            interval (int): The interval in seconds between task executions
        """
        super(BaseHTTPTask, self).__init__(agent, interval)
        self.endpoint = endpoint
        self._communication = None

    @property
    def communication(self):
        """
        Lazily instantiate and return
        the AgentCommunication object for this task.
        """
        if self._communication is None:
            self._communication = AgentCommunication(
                auth_token_type=self.agent.config.auth_token_type,
                post_data_fn=self.agent.post_data,
                get_data_fn=self.agent.get_data,
                controller_urls=self.agent.config.controller_urls,
            )
        return self._communication


class BaseGetTask(BaseHTTPTask):
    """
    Abstract base class for HTTP GET tasks.

    This class provides functionality for tasks that fetch data
    from HTTP endpoints using GET requests.
    """

    def __init__(self, agent, endpoint, interval):
        """
        Initialize the GET task.

        Args:
            agent (ServerAgent): The agent instance that owns this task
            endpoint (str): The HTTP endpoint URL to fetch data from
            interval (int): The interval in seconds between task executions
        """
        super(BaseGetTask, self).__init__(agent, endpoint, interval)
        self.data = NOT_FETCHED_YET

    def _fetch(self):
        """
        Fetch data from the HTTP endpoint.

        Uses the AgentCommunication class to retrieve data from the endpoint.
        The fetched data is stored in self.data.

        Returns:
            The fetched data from the endpoint
        """
        self.data = self.communication.get_data(
            endpoint=self.endpoint,
            max_retries=1,
            fail_silently=False,
            api_key=Authentication.get_key(),
        )
        return self.data

    def handle(self):
        """
        Handle the GET task execution.

        Fetches data from the endpoint and then processes it using
        the abstract _handle_fetched_data method.

        Returns:
            The result of processing the fetched data
        """
        self._fetch()
        return self._handle_fetched_data()

    @abc.abstractmethod
    def _handle_fetched_data(self):
        """
        Abstract method to process the fetched data.

        This method should be implemented by subclasses to define
        how the fetched data should be processed.

        Returns:
            The result of processing the data
        """
        pass


class BasePostTask(BaseHTTPTask):
    """
    Abstract base class for HTTP POST tasks.

    This class provides functionality for tasks that send data
    to HTTP endpoints using POST requests.
    """

    def __init__(self, agent, endpoint, interval):
        """
        Initialize the POST task.

        Args:
            agent: The agent instance that owns this task
            endpoint (str): The HTTP endpoint URL to send data to
            interval (int): The interval in seconds between task executions
        """
        super(BasePostTask, self).__init__(agent, endpoint, interval)
        self.payload = NOT_PRODUCED_YET

    def _post(self):
        """
        Send data to the HTTP endpoint.

        Uses the AgentCommunication class to send the payload to the endpoint.

        Returns:
            The response from the POST request
        """
        return self.communication.post_data(
            endpoint=self.endpoint,
            payload=self.payload,
            api_key=Authentication.get_key(),
            max_retries=1,
            fail_silently=False,
        )

    def handle(self):
        """
        Handle the POST task execution.

        Produces the payload using the abstract _produce_payload method
        and then sends it to the endpoint.

        Returns:
            The response from the POST request
        """
        self._produce_payload()
        return self._post()

    @abc.abstractmethod
    def _produce_payload(self):
        """
        Abstract method to produce the payload for the POST request.

        This method should be implemented by subclasses to define
        how the payload should be created.

        Returns:
            The payload to be sent in the POST request
        """
        pass
