import json
import os

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ServerStatus
from .serializers import ServerStatusResponseSerializer
from .utils import run_remote_health_check


@api_view(['POST'])
def receive_status(request):

    vm_ip = os.getenv('VM_SMTP_IP')
    username = os.getenv('VM_USERNAME')
    password = os.getenv('VM_PASSWORD')

    raw_data = run_remote_health_check(
        vm_ip,
        username=username,
        password=password
    )
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return Response(
            {'error': 'Invalid response from remote agent'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    server_status = ServerStatus.objects.create(
        hostname=data['hostname'],
        ip=data['ip'],
        uptime=data['uptime'],
        os=data['os'],
        server_name=data['server_name'],
        timestamp=data['timestamp'],
        healthy=data['healthy'],
    )

    response_serializer = ServerStatusResponseSerializer(server_status)
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)
