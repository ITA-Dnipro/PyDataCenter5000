import abc
import sys

from agents_infra.exceptions import TaskException


class BaseTask(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, agent, endpoint, interval, supervisor=None):
        self.agent = agent
        self.endpoint = endpoint
        self.interval = interval
        self.supervisor = supervisor

    def __call__(self):
        return self.handle()

    @abc.abstractmethod
    def handle(self):
        pass
