class BadProcessReturnCode(Exception):
    def __init__(self, message, returncode):
        super(BadProcessReturnCode, self).__init__(message)
        self.returncode = returncode


class PluginValidationError(Exception):
    pass


class PluginProtectedError(Exception):
    pass
