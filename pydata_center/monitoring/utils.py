from typing import Any, Dict

import requests
from django.http import HttpRequest

from .models import Webhook


def get_client_ip(request: HttpRequest) -> str:
    """
    Retrieve the client's IP address from the request object.
    If the application is behind a proxy, it tries to get the IP
    from the 'X-Forwarded-For' header.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def extract_status_data(
    data: Dict[str, Any],
    request: HttpRequest
) -> Dict[str, str]:
    """
    Extract status-related data from the request data and
    include the client IP if not provided.
    """
    return {
        'hostname': data.get('hostname', 'unknown'),
        'ip': data.get('ip') or get_client_ip(request),
        'uptime': data.get('uptime', 'unknown')
    }
