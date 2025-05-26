import os
from time import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ServerStatus
from .serializers import ServerStatusResponseSerializer, ServerStatusRequestSerializer
from .utils import run_remote_health_check
from drf_spectacular.utils import extend_schema


@extend_schema(
    request=ServerStatusRequestSerializer,
    responses=ServerStatusResponseSerializer,
    summary="Receive server status",
    description="Accepts a server status payload and stores it in the database.",
)
@api_view(['POST'])
def receive_status(request):
    serializer = ServerStatusRequestSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data

        vm_ip = os.getenv("VM_SMTP_IP")
        username = os.getenv("VM_USERNAME")
        password = os.getenv("VM_PASSWORD")

        healthy = run_remote_health_check(vm_ip, username=username, password=password)
        print(healthy)
        status = ServerStatus.objects.create(
            hostname=data['hostname'],
            ip=vm_ip,
            uptime=data['uptime'],
            os=data['os'],
            server_name=data['server_name'],
            timestamp=timezone.now(),
            healthy=healthy,
        )

        response_serializer = ServerStatusResponseSerializer(status)
        return Response(response_serializer.data, status=201)

    return Response(serializer.errors, status=400)

