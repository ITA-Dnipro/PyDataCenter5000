import json
import logging
import os
import sys

from agents_infra.agents import agent_factory
from agents_infra.supervisor import AgentSupervisor
from agents_infra.tasks import periodic_task_wrapper, task_factory

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)


def load_tasks_config():
    config_paths = [
        os.path.join(os.path.dirname(__file__), 'tasks_config.json'),
        os.path.join(os.path.dirname(__file__), 'tasks_config.json.template'),
    ]
    for path in config_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)


class AgentApp(object):

    def __init__(self, agent_name, task_configs=None):
        self.agent_name = agent_name
        self.agent = agent_factory(agent_name)
        self.supervisor = AgentSupervisor(self.agent)
        self.task_configs = task_configs or load_tasks_config()
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
    try:
        runner = AgentApp(agent_name, task_configs=load_tasks_config())
        runner.run()
    except ValueError as e:
        logging.getLogger('main').error(str(e), exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
