import abc


class BaseTask(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, agent, interval):
        self.agent = agent
        self.interval = interval

    def __call__(self):
        return self.handle()

    @abc.abstractmethod
    def handle(self):
        pass
