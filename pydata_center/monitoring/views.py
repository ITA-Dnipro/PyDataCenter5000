from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from .models import CommandHistory
from .serializers import CommandHistorySerializer
from rest_framework import viewsets, filters
from django.utils.timezone import now

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
        serializer.save(status='pending') #set default status
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def fetch_pending_command(request):
    hostname = request.query_params.get('hostname')

    if not hostname:
        return Response({'error': 'hostname is required'}, status=status.HTTP_400_BAD_REQUEST)
    command = CommandHistory.objects.filter(
        hostname=hostname,
        status='pending'
    ).order_by('timestamp').first()

    if not command:
        return Response({'message': 'No pending commands'}, status=status.HTTP_204_NO_CONTENT)
    
    serializer = CommandHistorySerializer(command)
    return Response(serializer.data)