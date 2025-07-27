from typing import Any, Dict

import jwt
from django.conf import settings
from django.http import HttpRequest

from .helpers import raise_invalid_token


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


def decode_agent_jwt(token: str) -> dict:
    """
    Decode and validate a JWT using the project’s secret key.

    Raises:
        AuthenticationFailed if the token is invalid or expired.
    Returns:
        Decoded JWT payload as dict.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
    except jwt.ExpiredSignatureError:
        raise raise_invalid_token('Token has expired.')
    except jwt.InvalidTokenError:
        raise raise_invalid_token('Invalid token.')
