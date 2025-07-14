import abc
import logging
import sys

from agents_infra.exceptions import TaskException
from agents_infra.utils.auth import Authentication


class BaseTask(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, agent, endpoint, interval, supervisor=None):
        self.agent = agent
        self.endpoint = endpoint
        self.interval = interval
        self.supervisor = supervisor

    def __call__(self):
        try:
            return self.handle()
        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if sys.version_info[0] < 3:
                # Python 2.x: use exec to avoid syntax error in Python 3
                exec(
                    "raise TaskException('Task %s failed: %s'), None, exc_tb" %
                    (self.__class__.__name__, exc_value)
                )
            else:
                # Python 3.x
                raise TaskException(
                    "Task '%s' failed: %s" %
                    (self.__class__.__name__, exc_value)
                ).with_traceback(exc_tb)

    @abc.abstractmethod
    def handle(self):
        pass


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


def task_factory(task_config, agent, supervisor=None):
    """Task factory to create task instances based on the configuration.

    Args:
        task_config (dict): A dictionary containing task configuration.
        agent (ServerAgent): An instance of the agent that
            the task will operate on.
        supervisor (AgentSupervisor, optional): A supervisor instance,
            if a task needs it. Defaults to None.

    Raises:
        ValueError: If the task name is unknown.

    Returns:
        BaseTask: A task instance based on the configuration.
    """
    name = task_config['name']
    endpoint = task_config['endpoint']
    interval = task_config['interval']
    if name == 'collect_and_send_status':
        return CollectAndSendStatusTask(agent, endpoint, interval, supervisor)
    elif name == 'collect_and_send_metrics':
        return CollectAndSendMetricsTask(agent, endpoint, interval, supervisor)
    # elif name == "fetch_command":
    #     return FetchCommandTask(agent, endpoint, interval, supervisor)
    # elif name == "execute_command":
    #     return ExecuteCommandTask(agent, endpoint, interval, supervisor)
    else:
        raise ValueError('Unknown task name: %s' % name)
