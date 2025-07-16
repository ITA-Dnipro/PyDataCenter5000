import pytest
from django.test.utils import override_settings


@pytest.fixture(scope='session')
def celery_config_override():
    """
    Custom Celery configuration for tests
    to avoid confusion with production settings.
    """
    return {
        'broker_url': 'redis://localhost:6379/0',
        'result_backend': 'redis://localhost:6379/0',
    }


@pytest.fixture(scope='session')
def celery_config(celery_config_override):
    """
    Alias for pytest-celery plugin to pick up our override.
    """
    return celery_config_override


@pytest.fixture(scope='session')
def celery_includes():
    """Modules where Celery tasks live."""
    return ['monitoring.tasks']


@pytest.fixture(autouse=True)
def mock_webhook_settings():
    """Prevent real network calls to Slack in tests."""
    with override_settings(
        ALERT_SLACK_WEBHOOK='https://hooks.slack.com/services/test/test/test'
    ):
        yield


@pytest.fixture(scope='function')
def celery_worker(celery_app):
    """
    Override the default celery_worker so it runs locally,
    not in a Docker container.
    """
    yield celery_app


@pytest.fixture(autouse=True)
def celery_always_eager(settings):
    """
    Force Celery into eager mode: .delay() executes synchronously.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
