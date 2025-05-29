import logging

from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import CommandHistory
from .serializers import (CommandHistorySerializer,
                          ServerStatusResponseSerializer)

logger = logging.getLogger('django')


@api_view(['POST'])
def receive_status(request):
    """
    Receive and log server status data sent via POST request.
    """
    serializer = ServerStatusResponseSerializer(data=request.data)

    if serializer.is_valid():
        try:
            serializer.save()
            validated = serializer.validated_data
            hostname = validated.get('hostname', 'unknown')
            ip = validated.get('ip', request.META.get('REMOTE_ADDR'))
            uptime = validated.get('uptime', 'unknown')

            logger.info(
                '[RECEIVED] Host: %s | IP: %s | Uptime: %s',
                hostname, ip, uptime
            )
            return Response(
                {
                    'message': 'Status received',
                    'hostname': hostname,
                    'ip': ip
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error('[ERROR] Saving status failed: %s', str(e))
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        ip = request.data.get('ip', request.META.get('REMOTE_ADDR'))
        hostname = request.data.get('hostname', 'unknown')

        logger.warning(
            '[INVALID] Host: %s | IP: %s | Errors: %s',
            hostname, ip, serializer.errors
        )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class CommandHistoryViewSet(viewsets.ModelViewSet):
    queryset = CommandHistory.objects.all()
    serializer_class = CommandHistorySerializer

    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ['hostname', 'status']
    ordering_fields = ['timestamp']

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = {
            key: value
            for key, value in request.data.items()
            if key in ['status', 'result']
        }
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = super().get_queryset()
        hostname = self.request.query_params.get('hostname')
        status = self.request.query_params.get('status')

        if hostname:
            queryset = queryset.filter(hostname=hostname)
        if status:
            queryset = queryset.filter(status=status)
        return queryset
