import logging

import requests
from monitoring.models import Webhook

logger = logging.getLogger(__name__)


def send_alert_to_webhooks(message):
    """
    Send messages to all active Slack
    webhooks from the database.
    """
    webhooks = Webhook.objects.filter(enabled=True)

    for hook in webhooks:
        try:
            payload = {'text': message}
            requests.post(hook.url, json=payload, timeout=5)
        except Exception as e:
            logger.error(
                f'[ERROR] Failed to send Slack alert to {hook.url}: {e}'
            )
