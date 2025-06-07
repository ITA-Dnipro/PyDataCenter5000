import logging
import operator
from datetime import timedelta
from functools import singledispatchmethod

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from monitoring.discord import DiscordMessage, send_async_discord_message
from monitoring.email import EmailMessage, send_async_email
from monitoring.models import AgentMetric, AlertRule

logger = logging.getLogger(__name__)

OPERATOR_MAP = {
    '>': operator.gt,
    '<': operator.lt,
    '==': operator.eq,
    '!=': operator.ne,
}

ALERT_DESTINATION_MAP = {
    'email': lambda rule, fail_silently=True, **kwargs: EmailMessage(
        subject=f'[{rule.metric.upper()} ALERT]',
        body=rule.notify_message,
        recepients=settings.ALERT_EMAIL_RECEPIENTS,
        sender=settings.ALERT_EMAIL_SENDER,
        **kwargs,
    ),
    'discord': lambda rule, **kwargs: DiscordMessage(
        content=f'[{rule.metric.upper()} ALERT] {rule.notify_message}',
        webhook=settings.ALERT_DISCORD_WEBHOOK,
    )
}


class AlertDispatcher:
    """Class responsible for routing alert messages."""
    @singledispatchmethod
    def send(self, message, **kwargs):
        pass

    @send.register
    def _(self, message: EmailMessage, **kwargs):
        send_async_email.apply_async(
            kwargs={
                'subject': message.subject,
                'body': message.body,
                'recepients': message.recepients,
                'sender': message.sender,
                'fail_silently': message.fail_silently,
            }
        )

    @send.register
    def _(self, message: DiscordMessage, **kwargs):
        send_async_discord_message.apply_async(
            kwargs={'content': message.content, 'webhook': message.webhook}
        )


# At the moment, a module-level singleton is sufficient.
dispatcher = AlertDispatcher()


@shared_task
def evaluate_agent_alerts():
    """Task to evaluate alert rules and trigger notification."""
    rules = AlertRule.objects.filter(is_active=True)

    for rule in rules:
        cache_key = f'alert_sent_{rule.id}'
        if cache.get(cache_key):
            continue  # Still in cooldown

        time_window_start = (
            timezone.now() - timedelta(minutes=rule.time_window_minutes)
        )
        data = AgentMetric.objects.filter(timestamp__gte=time_window_start)

        # Extract metric values from data
        values = [
            value for entry in data
            if (value := getattr(entry, rule.metric, None)) is not None
        ]

        if not values:
            logger.info(f'No data for rule: {rule}')

            continue

        avg = sum(values) / len(values)

        triggered = OPERATOR_MAP[rule.operator](avg, rule.threshold)

        if triggered:
            logger.warning(f'Alert triggered for rule: {rule}')
            logger.warning(f'Alert message: {rule.notify_message}')

            for destination in rule.destinations:
                factory = ALERT_DESTINATION_MAP.get(destination)
                if not factory:
                    logger.error(f'Unknown alert destination {destination}')
                    continue

                # In ALERT_DESTINATION_MAP, we use the combination of
                # parameters with default values and kwargs to pass optional
                # arguments to different factories.
                msg = factory(
                    rule, fail_silently=settings.ALERT_EMAIL_FAIL_SILENTLY
                )
                dispatcher.send(msg)

            cache.set(
                cache_key, True, timeout=settings.ALERT_RATE_LIMIT_SECONDS
            )
        else:
            logger.info(f'No alerts triggered since {time_window_start}')
