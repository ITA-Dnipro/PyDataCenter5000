from dataclasses import dataclass
from typing import Union

from celery import shared_task
from django.core.mail import send_mail


@shared_task
def send_async_email(
    subject: str,
    body: str,
    recepients: list,
    sender: Union[str, None] = None,
    fail_silently: bool = True,
):
    send_mail(
        subject=subject,
        message=body,
        recepient_list=recepients,
        from_email=sender,
        fail_silently=fail_silently,
    )


@dataclass
class EmailMessage:
    subject: str
    body: str
    recepients: list
    sender: Union[str, None] = None
    fail_silently: bool = True
