from agents_infra.tasks.periodic_mixin import PeriodicMixin
from agents_infra.utils import add_query_params
from agents_infra.utils.sysinfo import generate_report

from .base_http_task import BasePostTask


class CollectAndSendStatusTask(PeriodicMixin, BasePostTask):
    """
    Task for collecting and sending agent status to the controller.

    This task periodically collects the agent's status information
    and sends it to the controller endpoint.
    """

    def _produce_payload(self):
        """
        Produce the status payload for the POST request.

        Converts the agent's status to a dictionary format
        suitable for sending to the controller.

        Returns:
            dict: The agent's status information as a dictionary
        """
        status = self.agent.status_to_dict()
        self.payload = status
        return status


class CollectAndSendMetricsTask(PeriodicMixin, BasePostTask):
    """
    Task for collecting and sending system metrics to the controller.

    This task periodically collects system metrics using report util
    and sends them to the controller endpoint
    with the hostname as a query parameter.
    """

    def __init__(self, agent, endpoint, interval):
        """
        Initialize the metrics collection task.

        Args:
            agent (ServerAgent): The agent instance that owns this task
            endpoint (str): The HTTP endpoint URL to send metrics to
            interval (int): The interval in seconds between task executions
        """
        endpoint = add_query_params(endpoint, {'hostname': agent.hostname})
        super(CollectAndSendMetricsTask, self).__init__(
            agent=agent, endpoint=endpoint, interval=interval
        )

    def _produce_payload(self):
        """
        Produce the metrics payload for the POST request.

        Generates a system report and extracts specific metrics
        (CPU, RAM, disk, load average) for sending to the controller.

        Returns:
            dict: The system metrics as a dictionary
        """
        report = generate_report(self.agent.logger)
        payload = {}
        for k in ('cpu', 'ram', 'disk', 'load_avg'):
            if k in report:
                payload[k] = report[k]
        self.payload = payload
        return payload
