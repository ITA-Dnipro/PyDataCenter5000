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
