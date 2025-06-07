from dataclasses import dataclass

import requests
from celery import shared_task


@shared_task
def send_async_discord_message(content: str, webhook: str):
    response = requests.post(webhook, json={'content': content})
    response.raise_for_status()


@dataclass
class DiscordMessage:
    content: str
    webhook: str
