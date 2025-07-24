import base64
import logging
import os
import sys

from agents_infra.agents import agent_factory
from agents_infra.supervisor import AgentSupervisor
from agents_infra.tasks import periodic_task_wrapper, task_factory
from agents_infra.utils.logtools import maybe_log_message

DEBUG = True  # Set to True to run tasks directly for testing

# Hardcoded config for tasks
TASKS_CONFIG = [
    {
        'name': 'collect_and_send_status',
        'interval': 5,
        'endpoint': 'server/status/'
    }, {
        'name': 'collect_and_send_metrics',
        'interval': 5,
        'endpoint': 'agent/metrics/'
    }, {
        'name': 'fetch_command',
        'interval': 3,
        'endpoint': None
    }, {
        'name': 'execute_command',
        'interval': 2,
        'endpoint': None
    }
]


class AgentApp(object):

    def __init__(self, agent_name, task_configs=None):
        self.agent_name = agent_name
        self.agent = agent_factory(agent_name)
        self.supervisor = AgentSupervisor(self.agent)
        self.task_configs = task_configs or TASKS_CONFIG
        self.tasks = self.create_tasks()

    def create_tasks(self):
        return [
            task_factory(cfg, self.agent, self.supervisor)
            for cfg in self.task_configs
        ]

    def run(self):
        for task in self.tasks:
            wrapper = periodic_task_wrapper(
                task, task.interval, self.supervisor, min_delay=1, max_delay=2
            )
            self.supervisor.schedule(
                wrapper, min_delay=1, max_delay=2, timeout=2 * task.interval
            )
        self.supervisor.schedule_exit(min_delay=0.1, max_delay=1)
        self.supervisor.start()


def main():
    if len(sys.argv) != 2:
        logging.getLogger('main').error(
            'Usage: python -m agents_infra.main <agent_name>'
        )
        sys.exit(1)
    agent_name = sys.argv[1]
    if DEBUG:
        agent = agent_factory(agent_name)
        print('agent.config.url: %s' % agent.config.url)
        print('agent.config.url[repr]: %s' % repr(agent.config.url))
        tasks = [task_factory(cfg, agent) for cfg in TASKS_CONFIG]
        for task in tasks:
            try:
                print('Running task: %s' % task.__class__.__name__)
                result = task()
                print(
                    'Task %s completed successfully. Result: %s' %
                    (task.__class__.__name__, result)
                )
            except Exception as e:
                print('Task %s failed: %s' % (task.__class__.__name__, e))
        print('Exiting...')
    else:
        runner = AgentApp(agent_name)
        runner.run()


if __name__ == '__main__':
    main()
