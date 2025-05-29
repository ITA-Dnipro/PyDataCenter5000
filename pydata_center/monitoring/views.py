from django.shortcuts import render
from django.utils.timezone import now
from rest_framework import filters, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .models import CommandHistory
from .serializers import CommandHistorySerializer


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


@api_view(['POST'])
def create_command(request):
    serializer = CommandHistorySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(status='pending')  # set default status
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
def fetch_pending_command(request):
    hostname = request.query_params.get('hostname')

    if not hostname:
        return Response(
            {'error': 'hostname is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    command = CommandHistory.objects.filter(
        hostname=hostname,
        status='pending'
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
            {'error': 'id is required'},
            status=400
        )

    try:
        command = CommandHistory.objects.get(id=command_id)
    except CommandHistory.DoesNotExist:
        return Response(
            {'error': 'Command not found'},
            status=404
        )

    status_update = request.data.get('status')
    allowed_statuses = [choice[0] for choice in CommandHistory.STATUS_CHOICES]
    if status_update and status_update not in allowed_statuses:
        return Response(
            {'error': 'Invalid status value'},
            status=400
        )

    if status_update in ['done', 'failed']:
        command.timestamp = now()

    serializer = CommandHistorySerializer(
        command,
        data=request.data,
        partial=True
    )
    if serializer.is_valid():
        serializer.save()
        return Response(
            serializer.data,
            status=200
        )

    return Response(serializer.errors, status=400)
