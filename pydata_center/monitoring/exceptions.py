from rest_framework import status


class MonitoringBaseException(Exception):
    """
    The base exception for monitoring errors.

    Arguments:

    detail_info: Detailed information for logging or debugging.
    """
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        detail_info: str = ''
    ):
        super().__init__(message, detail_info, status_code)

    def __str__(self):
        message, detail_info, status_code = self.args
        return f'{message} (Status: {status_code}) | Details: {detail_info}'


class NoAuthUser(MonitoringBaseException):
    status_code = status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED
    message = 'User must be authenticated!'


class ResourceNotFound(MonitoringBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    message = 'The requested resource was not found.'


class PermissionDenied(MonitoringBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    message = 'You do not have permission to perform this action.'


class VMNotReachable(MonitoringBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = 'VM not reachable via TCP/SSH.'


class SSHConnectionFailed(MonitoringBaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = 'SSH connection failed.'
