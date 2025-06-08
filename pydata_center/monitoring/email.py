from dataclasses import dataclass
from typing import Union

from celery import shared_task
from django.core.mail import send_mail


@dataclass
class EmailMessage:
    subject: str
    body: str
    recepients: list
    sender: Union[str, None] = None
    fail_silently: bool = True


@shared_task
def send_async_email(message: EmailMessage):
    """
    Wraps Django's send_mail to send emails asynchronously.

    Parameters:
        message (EmailMessage): EmailMessage dataclass instance.
    """
    send_mail(
        subject=message.subject,
        message=message.body,
        recepient_list=message.recepients,
        from_email=message.sender,
        fail_silently=message.fail_silently,
    )
