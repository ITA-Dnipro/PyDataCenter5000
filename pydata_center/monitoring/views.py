import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import ServerStatusSerializer

logger = logging.getLogger('monitoring')


@api_view(['POST'])
def receive_status(request):
    serializer = ServerStatusSerializer(data=request.data)

    if serializer.is_valid():
        instance = serializer.save()
        logger.info(
            f'✅ Status received from {instance.hostname}'
            f' ({instance.ip}) - Healthy: {instance.healthy}'
        )
        return Response(
            {'message': 'Status received'},
            status=status.HTTP_201_CREATED
        )

    logger.warning(
        f'❌ Invalid status data from: {serializer.errors}'
    )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
