from datetime import timedelta

from .settings import *  # noqa: F403

# ─── DATABASE ───
#
# Use an in-memory SQLite database for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

#
# ─── CELERY ───
#
# Run Celery tasks synchronously (no broker required)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# If your project tries to read CELERY_BROKER_URL,
# point it to the dummy Redis URL:
CELERY_BROKER_URL = 'redis://localhost:6379/0'

#
# ─── DJANGO REST FRAMEWORK OVERRIDES ───
#
# Disable throttling in tests
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []  # noqa: F405
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}    # noqa: F405

#
# ─── SIMPLE JWT OVERRIDES ───
#
# Extend token lifetimes so tests don’t fail on expiration
SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] = timedelta(days=7)    # noqa: F405
SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'] = timedelta(days=30)  # noqa: F405

#
# ─── ALLOWED HOSTS ───
ALLOWED_HOSTS = ['*']

#
# ─── MISCELLANEOUS ───
#
# Turn off logging during tests so the console stays clean
LOGGING['disable_existing_loggers'] = True  # noqa: F405
