from django.db import connections
from django.db.utils import OperationalError
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import datetime


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
        db_conn.cursor()
        
        return Response({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.datetime.now().isoformat()
        })
    except OperationalError:
        return Response({
            'status': 'unhealthy',
            'database': 'disconnected',
            'timestamp': datetime.datetime.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 