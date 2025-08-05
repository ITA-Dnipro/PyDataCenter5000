import inspect
from copy import copy

from .command_tasks import FetchAndHandleCommandTask
from .gathering_tasks import (CollectAndSendMetricsTask,
                              CollectAndSendStatusTask)

TASK_REGISTRY = {
    'collect_and_send_status': CollectAndSendStatusTask,
    'collect_and_send_metrics': CollectAndSendMetricsTask,
    'fetch_and_handle_command': FetchAndHandleCommandTask,
}


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
    name = task_config.get('name')
    task_class = TASK_REGISTRY.get(name)
    if not task_class:
        raise ValueError('Unknown task name: %s' % name)

    attributes = copy(task_config)
    del attributes['name']
    attributes['agent'] = agent

    if supervisor:
        argspec = inspect.getargspec(task_class.__init__)
        if 'supervisor' in argspec.args:
            attributes['supervisor'] = supervisor

    return task_class(**attributes)
