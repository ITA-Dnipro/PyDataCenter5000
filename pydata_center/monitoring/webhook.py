import hashlib
import logging
import sys
from dataclasses import dataclass

import requests
from celery import shared_task

logger = logging.getLogger(__name__)


@dataclass
class WebhookMessage:
    content: str
    webhook: str
    fail_silently: bool = True


class SlackMessage(WebhookMessage):
    pass


class DiscordMessage(WebhookMessage):
    pass


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_async_webhook_message(self, message):
    """
    Send webhook message asynchronously with
    retry support.
    """
    try:
        response = requests.post(
            message.webhook,
            json={'text': message.content},
            timeout=5
        )
        response.raise_for_status()

        if response.status_code not in [200, 204]:
            logger.warning(
                f'Unexpected webhook response: '
                f'{response.status_code} {response.text}'
            )
        else:
            logger.info(
                f'POST request sent successfully. '
                f'Webhook response: {response.status_code} {response.text}'
            )

    except requests.RequestException as e:
        logger.warning(
            f'[RETRY] Transient error sending to {message.webhook}: {e}'
        )
        raise self.retry(exc=e)

    except Exception as e:
        logger.error(
            f'Sending webhook message failed due to error: {sys.exc_info()[0]}'
        )
        webhook_hash = hashlib.sha256(
            message.webhook.encode()
        ).hexdigest()[:8]

        logger.error(f'Webhook hash: {webhook_hash}')

        if not message.fail_silently:
            raise type(e)('Sending Webhook message failed. ')
