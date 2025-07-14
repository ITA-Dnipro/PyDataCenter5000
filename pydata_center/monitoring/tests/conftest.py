import pytest
from django.test.utils import override_settings


@pytest.fixture(scope='session')
def celery_config():
    return {
        'broker_url': 'redis://localhost:6379/0',
        'result_backend': 'redis://localhost:6379/0',
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
    """
    Override the default celery_worker so it does NOT build a Docker image,
    and instead just yields celery_app in the same process.
    """
    yield celery_app


@pytest.fixture(autouse=True)
def celery_always_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
