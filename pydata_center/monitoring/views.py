import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import ServerStatusResponseSerializer

logger = logging.getLogger('django')


@api_view(['POST'])
def receive_status(request):
    """
    Receive and log server status data sent via POST request.
    """
    serializer = ServerStatusResponseSerializer(data=request.data)

    hostname = request.data.get('hostname', 'unknown')
    ip = request.data.get('ip', request.META.get('REMOTE_ADDR'))
    uptime = request.data.get('uptime', 'unknown')

    if serializer.is_valid():
        serializer.save()
        logger.info(
            '[RECEIVED] Host: %s | IP: %s | Uptime: %s',
            hostname, ip, uptime
        )
        return Response(
            {'message': 'Status received'},
            status=status.HTTP_201_CREATED
        )
    else:
        logger.warning(
            '[INVALID] Host: %s | IP: %s | Errors: %s',
            hostname, ip, serializer.errors
        )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
