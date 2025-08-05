import abc


class BaseTask(object):
    """
    Abstract base class for all tasks in the agent infrastructure.

    This class defines the interface that all tasks must implement.
    Tasks are callable objects that perform specific operations
    at regular intervals.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, agent):
        """
        Initialize the base task.

        Args:
            agent (ServerAgent): The agent instance that owns this task
            interval (int): The interval in seconds between task executions
        """
        self.agent = agent

    def __call__(self):
        """
        Make the task callable.

        Returns:
            The result of the task's handle method
        """
        return self.handle()

    @abc.abstractmethod
    def handle(self):
        """
        Abstract method that must be implemented by subclasses.

        This method should contain the main logic for the task.
        It will be called when the task is executed.

        Returns:
            The result of the task execution
        """
        pass
