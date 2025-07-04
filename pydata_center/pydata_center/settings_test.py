from datetime import timedelta

from .settings import *  # noqa: F403

REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = []  # noqa: F405
REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = [  # noqa: F405
    'rest_framework.permissions.AllowAny',
]
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []  # noqa: F405
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}  # noqa: F405


SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] = timedelta(days=7)  # noqa: F405
SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'] = timedelta(days=30)  # noqa: F405

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
