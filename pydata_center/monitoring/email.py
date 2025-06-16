import logging
from dataclasses import dataclass
from typing import Union

from celery import shared_task
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    subject: str
    body: str
    recipients: list
    sender: Union[str, None] = None
    fail_silently: bool = True


@shared_task
def send_async_email(message):
    """
    Wraps Django's send_mail to send emails asynchronously.

    Parameters:
        message (Any): Instance of EmailMessage (if function is called
            explicitly) or JSON-serialized EmailMessage.
    """
    try:
        if not isinstance(message, EmailMessage):
            message = EmailMessage(**message)

        send_mail(
            subject=message.subject,
            message=message.body,
            recipient_list=message.recipients,
            from_email=message.sender,
            fail_silently=message.fail_silently,
        )
    except TypeError as e:
        logger.error(f'Error due to missing or invalid arguments: {e}')
