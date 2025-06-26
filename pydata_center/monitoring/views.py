import logging

from django.contrib.auth.decorators import permission_required
from django.db.models import Q
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware, now, utc
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiParameter, OpenApiResponse,
                                   extend_schema, extend_schema_view)
from monitoring.permissions import IsAdminOrOperatorForWrite
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .alerts import (alert_if_command_failed, alert_if_unhealthy,
                     alert_on_success)
from .helpers import get_latest_agents
from .models import AgentMetric, CommandHistory, ServerStatus, TriggeredAlert
from .serializers import (AgentMetricSerializer, CommandHistorySerializer,
                          ServerStatusSerializer, TriggeredAlertSerializer)
from .utils import extract_status_data, get_client_ip

logger = logging.getLogger(__name__)


@extend_schema(
        tags=['Server Status'],
        request=ServerStatusSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                description='Status received and logged.'
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description='Invalid data.'
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description='Internal server error.'
            ),
        },
        description='Receive and log server status data sent via POST request.'
)
@api_view(['POST'])
@permission_required('monitoring.add_serverstatus', raise_exception=True)
def receive_status(request):
    """
    Receive and log server status data sent via POST request.
    """
    serializer = ServerStatusSerializer(data=request.data)

    if serializer.is_valid():
        try:
            serializer.save()
            data = extract_status_data(serializer.validated_data, request)
            healthy = serializer.validated_data.get('healthy', False)
            alert_if_unhealthy(data['hostname'], healthy)
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


@extend_schema_view(
    list=extend_schema(
        description=(
            'List of all command records.'
            'Supports filtering by hostname and status.'
        ),
        parameters=[
            OpenApiParameter(
                name='status',
                type=str, location=OpenApiParameter.QUERY,
                enum=[choice[0] for choice in CommandHistory.STATUS_CHOICES],
                description='Filter by command status'
            ),
        ],
        responses=CommandHistorySerializer(many=True),
        tags=['Command'],
    ),
    retrieve=extend_schema(
        description='Get a specific command record by ID.',
        responses=CommandHistorySerializer,
        tags=['Command'],
    ),
    create=extend_schema(
        description=(
            'Create a new command record.'
            'Status will be set to \'pending\' by default.'
        ),
        responses=CommandHistorySerializer,
        tags=['Command'],
    ),
    partial_update=extend_schema(
        description='Update command status or result (partial).',
        responses=CommandHistorySerializer,
        tags=['Command'],
    ),
    destroy=extend_schema(
        description='Delete command record by ID.',
        tags=['Command'],
    ),
)
class CommandHistoryViewSet(viewsets.ModelViewSet):
    queryset = CommandHistory.objects.all()
    serializer_class = CommandHistorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrOperatorForWrite]

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

        result = data.get('result', '')
        command_status = data.get('status')

        alert_if_command_failed(instance.hostname, result)

        if command_status == 'done' and instance.notify_on_success:
            alert_on_success(instance.hostname, result)

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


@extend_schema(
    tags=['Command'],
    description='Agent fetches a pending command by providing its hostname.',
    parameters=[
        OpenApiParameter(
            name='hostname',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Unique hostname of the agent.'
        )
    ],
    responses={
        status.HTTP_200_OK: CommandHistorySerializer,
        status.HTTP_204_NO_CONTENT: OpenApiResponse(
            description='No pending commands'
        ),
        status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            description='Hostname is required'
        ),
    }
)
@api_view(['GET'])
def fetch_pending_command(request):
    """
    Endpoint for agents to request pending commands.
    Returns the earliest command with status 'pending'
    for the given hostname.
    """
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


@extend_schema(
        tags=['Command'],
        request=CommandHistorySerializer,
        responses={
            status.HTTP_200_OK: CommandHistorySerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description='Validation error or invalid status'
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description='Command not found or ID missing'
            ),
        },
        description=(
            'Agent submits the result or status update for a command by ID.'
        ),
)
@api_view(['PATCH'])
def submit_command_result(request):
    command_id = request.data.get('id')
    if not command_id:
        return Response(
            {'error': 'id is required'},
            status=status.HTTP_404_NOT_FOUND
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

        final_status = serializer.validated_data.get('status', status_update)
        final_result = serializer.validated_data.get('result', '')

        alert_if_command_failed(command.hostname, final_result)

        if final_status == 'done' and command.notify_on_success:
            alert_on_success(command.hostname, final_result)

        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@permission_required('monitoring.view_serverstatus', raise_exception=True)
def dashboard_view(request):
    """
    Render the monitoring dashboard page.
    Standard Django HTML view, not part of API.
    """
    agents = get_latest_agents()

    return render(
        request,
        template_name='monitoring/dashboard.html',
        context={'agents': agents}
    )


@api_view(['POST'])
def create_agent_metric(request):
    hostname = request.query_params.get('hostname')

    if not hostname:
        return Response({'error': 'Hostname is required'}, status=400)

    try:
        server_status = ServerStatus.objects.get(hostname=hostname)
    except ServerStatus.DoesNotExist:
        return Response(
            {'error': f'Server with hostname {hostname} not found'},
            status=404
        )

    data = request.data.copy()
    data['server_status'] = server_status.id

    serializer = AgentMetricSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response({'status': 'metric recorded'}, status=201)
    return Response(serializer.errors, status=400)


class TriggeredAlertViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TriggeredAlert.objects.order_by('-triggered_at')
    serializer_class = TriggeredAlertSerializer


@extend_schema(
    tags=['Metrics'],
    parameters=[
        OpenApiParameter(
            name='hostname',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Hostname of the server to filter metrics.'
        ),
        OpenApiParameter(
            name='start',
            type=OpenApiTypes.DATETIME,
            location=OpenApiParameter.QUERY,
            description='Start datetime (ISO 8601) for metrics filtering.'
        ),
        OpenApiParameter(
            name='end',
            type=OpenApiTypes.DATETIME,
            location=OpenApiParameter.QUERY,
            description='End datetime (ISO 8601) for metrics filtering.'
        ),
    ],
    responses={
        status.HTTP_200_OK: OpenApiResponse(
            description='List of filtered agent metrics.'
        ),
        status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            description='Invalid datetime format or query parameters.'
        ),
    },
    description=(
        'Returns historical server metrics (CPU, RAM, disk usage, '
        'load average) based on optional filters: hostname, '
        'start time, and end time.'
    ),
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

    if start_str and not start:
        raise ValidationError({'start': 'Invalid datetime format.'})
    if end_str and not end:
        raise ValidationError({'end': 'Invalid datetime format.'})

    if start and is_naive(start):
        start = make_aware(start, timezone=utc)
    if end and is_naive(end):
        end = make_aware(end, timezone=utc)

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


def metrics_graphing_page(request):
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


class ServerStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for ServerStatus.
    Returns all ServerStatus records, including
    prediction_flag and nested metrics.
    """
    queryset = ServerStatus.objects.all().order_by('-created_at')
    serializer_class = ServerStatusSerializer
