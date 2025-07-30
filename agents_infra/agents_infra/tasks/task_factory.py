from .command_tasks import FetchAndHandleCommandTask
from .gathering_tasks import (CollectAndSendMetricsTask,
                              CollectAndSendStatusTask)


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
    endpoint = task_config.get('endpoint')
    interval = task_config.get('interval')
    if name == 'collect_and_send_status':
        return CollectAndSendStatusTask(
            agent=agent, endpoint=endpoint, interval=interval
        )
    elif name == 'collect_and_send_metrics':
        return CollectAndSendMetricsTask(
            agent=agent, endpoint=endpoint, interval=interval
        )
    elif name == 'fetch_and_handle_command':
        return FetchAndHandleCommandTask(
            agent=agent,
            endpoint=endpoint,
            interval=interval,
            supervisor=supervisor
        )
    else:
        raise ValueError('Unknown task name: %s' % name)
