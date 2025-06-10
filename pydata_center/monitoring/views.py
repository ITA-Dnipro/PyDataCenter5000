import logging

from django.shortcuts import render
from django.utils.timezone import now
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiParameter, OpenApiResponse,
                                   extend_schema, extend_schema_view)
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .helpers import get_latest_agents
from .models import CommandHistory
from .serializers import CommandHistorySerializer, ServerStatusSerializer
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
