import pytest
from django.test.utils import override_settings


@pytest.fixture(scope='session')
def celery_broker():
    return 'redis://localhost:6379/0'


@pytest.fixture(scope='session')
def celery_backend():
    return 'redis://localhost:6379/0'


@pytest.fixture(autouse=True)
def mock_webhook_settings():
    with override_settings(
        ALERT_SLACK_WEBHOOK='https://hooks.slack.com/services/test/test/test'
    ):
        yield
