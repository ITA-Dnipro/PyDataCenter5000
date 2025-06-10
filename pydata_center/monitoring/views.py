import logging

from django.db.models import Q
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils.timezone import (get_current_timezone, is_naive, make_aware,
                                   now)
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .helpers import get_latest_agents
from .models import AgentMetric, CommandHistory, ServerStatus
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

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['status'] = 'pending'
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        return Response(
            {'error': 'id is required'}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        command = CommandHistory.objects.get(id=command_id)
    except CommandHistory.DoesNotExist:
        return Response(
            {'error': 'Command not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    status_update = request.data.get('status')
    allowed_statuses = [choice[0] for choice in CommandHistory.STATUS_CHOICES]
    if status_update and status_update not in allowed_statuses:
        return Response(
            {'error': 'Invalid status value'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if status_update in ['done', 'failed']:
        command.timestamp = now()

    serializer = CommandHistorySerializer(
        command, data=request.data, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def dashboard_view(request):
    agents = get_latest_agents()

    return render(
        request,
        template_name='monitoring/dashboard.html',
        context={'agents': agents}
    )


@api_view(['GET'])
def metrics_history_view(request):
    """
    Returns historical server metrics as JSON.
    Processes a GET request with optional `hostname`, `start`, and `end`
    parameters. Filters the ServerStatus records based on the provided
    criteria and returns a list of metrics (CPU, RAM, disk usage, load
    average) within the specified time range.
    """
    hostname = request.GET.get('hostname')
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    start = parse_datetime(start_str) if start_str else None
    end = parse_datetime(end_str) if end_str else None

    tz = get_current_timezone()
    if start and is_naive(start):
        start = make_aware(start, tz)
    if end and is_naive(end):
        end = make_aware(end, tz)

    filters = Q()
    if hostname:
        filters &= Q(server_status__hostname=hostname)
    if start:
        filters &= Q(timestamp__gte=start)
    if end:
        filters &= Q(timestamp__lte=end)

    records = (
        AgentMetric.objects
        .filter(filters)
        .select_related('server_status')
        .order_by('timestamp')
        .values(
            'timestamp',
            'cpu',
            'ram',
            'disk',
            'load_avg',
            'server_status__hostname'
        )
    )
    return Response(records)


def metrics_graphing_view(request):
    hostnames = (
        ServerStatus.objects
        .values_list('hostname', flat=True)
        .distinct()
    )
    return render(
        request,
        'historical_metrics.html',
        {'hostnames': hostnames}
    )
