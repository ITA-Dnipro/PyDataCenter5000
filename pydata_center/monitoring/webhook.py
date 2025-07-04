import logging
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
    Send webhook message asynchronously with retry support.
    """

    if isinstance(message, dict):
        try:
            message = WebhookMessage(**message)
        except (TypeError, ValueError):
            logger.error('Error due to missing or invalid arguments')
            return None

    try:
        response = requests.post(
            message.webhook,
            json={'text': message.content},
            timeout=getattr(message, 'timeout', 5)
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            f'Sending message to webhook failed due to error: {type(e)}'
        )
        if not getattr(message, 'fail_silently', False):

            raise
        return None
    except (requests.exceptions.ConnectionError,
            requests.exceptions.InvalidURL) as e:
        logger.error(
            f'Sending message to webhook failed due to error: {type(e)}'
        )
        return None

    if response.status_code not in (200, 204):
        logger.warning(
            (
                f'Unexpected webhook response: '
                f'{response.status_code} {response.text} '
            )
        )
    else:
        logger.info(
            (
                f'POST request sent successfully. '
                f'Webhook response: {response.status_code} {response.text} '
            )
        )
    return None
