import os

import pytest
from django.test.utils import override_settings


def pytest_addoption(parser):
    parser.addoption(
        '--redis-url',
        action='store',
        default=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        help='Redis URL for Celery broker/backend'
    )


@pytest.fixture(scope='session')
def celery_config(request):
    """
    Read broker/result_backend URL
    from CLI option or REDIS_URL env var.
    """
    redis_url = request.config.getoption('--redis-url')
    return {
        'broker_url': redis_url,
        'result_backend': redis_url,
    }


@pytest.fixture(scope='session')
def celery_includes():
    return ['monitoring.tasks']


@pytest.fixture(autouse=True)
def mock_webhook_settings():
    with override_settings(
        ALERT_SLACK_WEBHOOK='https://hooks.slack.com/services/test/test/test'
    ):
        yield


@pytest.fixture(scope='function')
def celery_worker(celery_app):
    yield celery_app


@pytest.fixture(autouse=True)
def celery_always_eager(settings):
    """
    Ensures Celery tasks run synchronously and exceptions propagate.
    Useful for testing task logic directly without involving a worker.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
