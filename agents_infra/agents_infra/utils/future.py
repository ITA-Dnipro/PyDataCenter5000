import threading


class Future:
    def __init__(self, func, *args, **kwargs):
        self._done = False
        self._result = None
        self._exception = None

        def wrapper():
            try:
                self._result = func(*args, **kwargs)
            except Exception as e:
                self._exception = e
            finally:
                self._done = True

        self._thread = threading.Thread(target=wrapper)
        self._thread.daemon = True
        self._thread.start()

    def done(self):
        return self._done

    def result(self):
        if not self._done:
            raise RuntimeError('Task is not finished yet')
        if self._exception:
            raise self._exception
        return self._result

    def cancel(self):
        if self._done:
            return False
        self._exception = RuntimeError('Task was cancelled')
        self._done = True
        return True
