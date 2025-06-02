import logging
from typing import Any, Dict, Union

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import MonitoringBaseException

log = logging.getLogger(__name__)


def custom_exception_handler(
    exc: Union[MonitoringBaseException, Exception],
    context: Dict[str, Any]
) -> Response:

    if isinstance(exc, MonitoringBaseException):
        if exc.detail_info:
            log.error(exc.message)
            return Response(
                {'error': exc.message, 'detail': exc.detail_info},
                status=exc.status_code
            )
        return Response({'error': exc.message}, status=exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data['status_code'] = response.status_code
        return response

    log.error('Unhandled exception %s', exc, exc_info=exc)
    return Response(
        {'error': 'Unknown error occurred'},
        status=status.HTTP_400_BAD_REQUEST
    )
