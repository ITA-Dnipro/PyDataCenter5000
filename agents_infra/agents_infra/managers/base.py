import abc


class ServerManager:
    __metaclass__ = abc.ABCMeta

    def start(self):
        raise NotImplementedError('Subclasses must implement start()')

    def stop(self):
        raise NotImplementedError('Subclasses must implement stop()')
