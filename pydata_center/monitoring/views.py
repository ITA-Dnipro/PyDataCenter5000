import logging

from django.shortcuts import render
from django.utils.timezone import now
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .helpers import get_latest_agents
from .models import CommandHistory
from .serializers import CommandHistorySerializer, ServerStatusSerializer
from .utils import extract_status_data, get_client_ip

logger = logging.getLogger(__name__)


@api_view(['POST'])
def receive_status(request):
    """
    Receive and log server status data sent via POST request.
    """
    serializer = ServerStatusSerializer(data=request.data)

    if serializer.is_valid():
        try:
            serializer.save()
            data = extract_status_data(serializer.validated_data, request)
            logger.info(
                '[RECEIVED] Host: %s | IP: %s | Uptime: %s',
                data['hostname'], data['ip'], data['uptime']
            )
            return Response(
                {
                    'message': 'Status received',
                    'hostname': data['hostname'],
                    'ip': data['ip']
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
        data = extract_status_data(request.data, request)
        logger.warning(
            '[INVALID] Host: %s | IP: %s | Errors: %s',
            data['hostname'], data['ip'], serializer.errors
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


@api_view(['POST'])
def create_command(request):
    serializer = CommandHistorySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(status='pending')  # set default status
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def fetch_pending_command(request):
    hostname = request.query_params.get('hostname')

    if not hostname:
        return Response(
            {'error': 'hostname is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    command = CommandHistory.objects.filter(
        hostname=hostname, status='pending'
    ).order_by('timestamp').first()

    if not command:
        return Response(
            {'message': 'No pending commands'},
            status=status.HTTP_204_NO_CONTENT
        )

    serializer = CommandHistorySerializer(command)
    return Response(serializer.data)


@api_view(['PATCH'])
def submit_command_result(request):
    command_id = request.data.get('id')
    if not command_id:
        return Response({'error': 'id is required'}, status=400)

    try:
        command = CommandHistory.objects.get(id=command_id)
    except CommandHistory.DoesNotExist:
        return Response({'error': 'Command not found'}, status=404)

    status_update = request.data.get('status')
    allowed_statuses = [choice[0] for choice in CommandHistory.STATUS_CHOICES]
    if status_update and status_update not in allowed_statuses:
        return Response({'error': 'Invalid status value'}, status=400)

    if status_update in ['done', 'failed']:
        command.timestamp = now()

    serializer = CommandHistorySerializer(
        command, data=request.data, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=200)

    return Response(serializer.errors, status=400)


def dashboard_view(request):
    agents = get_latest_agents()

    return render(
        request,
        template_name='monitoring/dashboard.html',
        context={'agents': agents}
    )
