class BadProcessReturnCode(Exception):
    pass


class AuthenticationError(Exception):
    def __init__(self, message, server_name=None):
        if server_name:
            message = '[%s] %s' % (server_name, message)
        super(AuthenticationError, self).__init__(message)
        self.server_name = server_name
