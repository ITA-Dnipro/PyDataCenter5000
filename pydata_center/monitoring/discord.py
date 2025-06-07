import logging
from dataclasses import dataclass

import requests
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_async_discord_message(
    content: str, webhook: str, fail_silently: bool = True
):
    """
    Send Discord message asynchronously using provided webhook.

    Parameters:
        content (str): Message content.
        webhook (str): Discord channel's webhook.
        fail_silently (bool, optional): Whether to silence an exceptions
            if any. Default is True.
    """
    try:
        response = requests.post(webhook, json={'content': content})
        response.raise_for_status()
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.InvalidURL,
        requests.exceptions.HTTPError,
    ) as e:
        logger.error(f'Sending Discord message failed due to error: {e}')

        if not fail_silently:
            raise


@dataclass
class DiscordMessage:
    content: str
    webhook: str
    fail_silently: bool = True
