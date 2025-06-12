import logging

import requests
from celery import shared_task
from monitoring.models import Webhook

logger = logging.getLogger(__name__)


def send_alert_to_webhooks(message):
    """
    Send messages to all active Slack
    webhooks from the database.
    """
    webhooks = Webhook.objects.filter(enabled=True)

    for hook in webhooks:
        async_send_to_webhook.delay(hook.url, message)


@shared_task
def async_send_to_webhook(url, message):
    """
    Asynchronously send a Slack message to
    the given webhook URL.
    """
    try:
        response = requests.post(url, json={'text': message}, timeout=5)
        response.raise_for_status()

        logger.info(
            f'[Slack] Message sent to {url} – status {response.status_code}'
        )
    except Exception as e:
        logger.error(f'[Slack ERROR] Failed to send message to {url}: {e}')
