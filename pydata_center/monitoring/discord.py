import logging
from dataclasses import dataclass

import requests
from celery import shared_task

logger = logging.getLogger(__name__)


@dataclass
class DiscordMessage:
    content: str
    webhook: str
    fail_silently: bool = True


@shared_task
def send_async_discord_message(message: DiscordMessage):
    """
    Send Discord message asynchronously using provided webhook.

    Parameters:
        message (DiscordMessage): DiscordMessage dataclass instance.
    """
    try:
        response = requests.post(
            message.webhook, json={'content': message.content}
        )
        response.raise_for_status()
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.InvalidURL,
        requests.exceptions.HTTPError,
    ) as e:
        logger.error(f'Sending Discord message failed due to error: {e}')

        if not message.fail_silently:
            raise
