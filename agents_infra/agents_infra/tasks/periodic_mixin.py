class PeriodicMixin(object):

    def __init__(self, interval, *args, **kwargs):
        self._interval = interval
        self.interval = interval
        super(PeriodicMixin, self).__init__(*args, **kwargs)

    @property
    def interval(self):
        """
        Returns the interval in seconds between task executions.
        """
        return self._interval

    @interval.setter
    def interval(self, value):
        """
        Sets the interval in seconds between task executions.

        Args:
            value (int or float): The interval in seconds.
        """
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError('Interval must be a positive number.')
        self._interval = value
