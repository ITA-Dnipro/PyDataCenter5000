import hashlib
import logging
import sys
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
            message['webhook'], json={'content': message['content']}
        )
        response.raise_for_status()

        if response.status_code not in [200, 204]:
            logger.warning(
                f'Unexpected Discord reponse: '
                f'{response.status_code} {response.text}'
            )
        else:
            logger.info(
                f'POST request sent succesfully. Discord reposnse: '
                f'{response.status_code} {response.text}'
            )
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.InvalidURL,
        requests.exceptions.HTTPError,
    ) as e:
        logger.error(
            f'Sending Discord message failed due to error: {sys.exc_info()[0]}'
        )
        # Identify possibly problematic webhook.
        logger.error(
            f'Webhook hash: '
            f'{hashlib.sha256(message["webhook"].encode()).hexdigest()[:8]}'
        )

        if not message['fail_silently']:
            raise type(e)('Sending Discord message failed.')
