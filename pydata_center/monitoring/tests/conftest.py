import pytest
from django.test.utils import override_settings


@pytest.fixture(autouse=True)
def slack_webhook_setting():
    with override_settings(
        ALERT_SLACK_WEBHOOK='https://hooks.slack.com/services/test/test/test'
    ):
        yield
