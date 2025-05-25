import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from time import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ServerStatus
from .serializers import ServerStatusResponseSerializer, ServerStatusRequestSerializer
from agents.smtp import SMTPAgent


@api_view(['POST'])
def receive_status(request):
    request_serializer = ServerStatusRequestSerializer(data=request.data)
    if request_serializer.is_valid():
        data = request_serializer.validated_data

        if data['server_name'] == "smtp":
            agent = SMTPAgent(ip=data['ip'], hostname=data['hostname'])
            healthy = agent.service_healthy()
        else:
            healthy = False  # Or handle other types

        # Save to DB using the full model serializer
        status = ServerStatus.objects.create(
            hostname=data['hostname'],
            ip=data['ip'],
            uptime=data['uptime'],
            os=data['os'],
            server_name=data['server_name'],
            timestamp=timezone.now(),
            healthy=healthy,
        )

        response_serializer = ServerStatusResponseSerializer(status)
        return Response(response_serializer.data, status=201)

    return Response(request_serializer.errors, status=400)
