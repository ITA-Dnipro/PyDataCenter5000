import pytest
from django.test.utils import override_settings


@pytest.fixture(autouse=True)
def mock_webhook_settings():
    with override_settings(
        ALERT_SLACK_WEBHOOK='https://hooks.slack.com/services/test/test/test'
    ):
        yield
