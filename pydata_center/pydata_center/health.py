import logging

from django.db import connections
from django.db.utils import OperationalError
from django.utils.timezone import now
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@extend_schema(
        responses={
            200: OpenApiResponse(
                description='Database and application are available.'
            ),
            503: OpenApiResponse(description='Database connection failed.'),
            500: OpenApiResponse(description='Unexpected health check error.')
        },
        description=(
            'Health check endpoint that verifies'
            'application and database availability.'
        ),
)
@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint that verifies:
    1. Application is running
    2. Database connection is working
    """
    try:
        # Check database connection
        db_conn = connections['default']
        db_conn.ensure_connection()
        return Response(
            {
                'status': 'healthy',
                'database': 'connected',
                'timestamp': now().isoformat(),
            }
        )
    except OperationalError as e:
        logger.warning(f'Database connection failed: {e}')
        return Response(
            {
                'status': 'unhealthy',
                'database': 'disconnected',
                'timestamp': now().isoformat(),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as e:
        logger.error(f'Unexpected error in health check: {e}', exc_info=True)
        return Response(
            {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': now().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
