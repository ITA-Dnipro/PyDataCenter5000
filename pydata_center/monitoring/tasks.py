import logging
import operator
from datetime import timedelta
from functools import singledispatchmethod
from typing import Union

import requests
from celery import group, shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from monitoring.discord import DiscordMessage, send_async_discord_message
from monitoring.email import EmailMessage, send_async_email
from monitoring.models import AgentMetric, AlertRule
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

OPERATOR_MAP = {
    '>': operator.gt,
    '<': operator.lt,
    '==': operator.eq,
    '!=': operator.ne,
}

ALERT_DESTINATION_MAP = {
    'email': lambda subject, body, fail_silently=True: EmailMessage(
        subject=subject,
        body=body,
        recipients=settings.ALERT_EMAIL_RECIPIENTS,
        sender=settings.ALERT_EMAIL_SENDER,
        fail_silently=fail_silently,
    ),
    'discord': lambda subject, body, fail_silently=True: DiscordMessage(
        content=f'{subject} {body}',
        webhook=settings.ALERT_DISCORD_WEBHOOK,
        fail_silently=fail_silently,
    )
}


class AlertDispatcher:
    """Class responsible for routing alert messages."""
    @singledispatchmethod
    def send(self, message, **kwargs):
        pass

    @send.register
    def _(self, message: EmailMessage, **kwargs):
        send_async_email.apply_async(kwargs={'message': message})

    @send.register
    def _(self, message: DiscordMessage, **kwargs):
        send_async_discord_message.apply_async(kwargs={'message': message})


# At the moment, a module-level singleton is sufficient.
dispatcher = AlertDispatcher()


@shared_task
def evaluate_agent_alerts(
    destinations: Union[list, None] = None, batch: bool = True
):
    """
    Task to evaluate alert rules and trigger notification.

    Parameters:
        destinations (list, optional): List of alert destinations, e.g.,
            ['email', 'discord]. If not provided, DEFAULT_ALERT_DESTINATIONS
            is used.
        batch (bool, optional): Whether to send all alerts triggered
            withing a time window in a batch. True by default.
    """
    if destinations is None:
        destinations = settings.DEFAULT_ALERT_DESTINATIONS

    triggered_alerts = []

    rules = AlertRule.objects.filter(is_active=True)

    for rule in rules:
        cache_key = f'alert_sent_{rule.id}'
        if cache.get(cache_key):
            continue  # Still in cooldown

        time_window_start = (
            timezone.now() - timedelta(minutes=rule.time_window_minutes)
        )

        filters = {'timestamp__gte': time_window_start}
        if rule.hostname:
            filters['server_status__hostname'] = rule.hostname

        data = AgentMetric.objects.filter(**filters)

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

            if batch:
                triggered_alerts.append(rule)
            else:
                for destination in destinations:
                    factory = ALERT_DESTINATION_MAP.get(destination)
                    if not factory:
                        logger.error(
                            f'Unknown alert destination {destination}'
                        )
                        continue

                    # In ALERT_DESTINATION_MAP, we use the combination of
                    # parameters with default values and kwargs to pass
                    # optional arguments to different factories.
                    msg = factory(
                        subject=f'[{rule.metric.upper()} ALERT]',
                        body=rule.notify_message,
                        fail_silently=settings.ALERT_FAIL_SILENTLY,
                    )
                    dispatcher.send(msg)

                cache.set(
                    cache_key, True, timeout=settings.ALERT_RATE_LIMIT_SECONDS
                )
        else:
            logger.info(f'No alerts triggered since {time_window_start}')

    # Send all alerts triggered within a time window in a batch.
    if triggered_alerts:
        subject = (
            f'{len(triggered_alerts)} Alert(s) Triggered Since '
            f'{time_window_start}\n\n'
        )
        summary = '\n'.join(
            [
                f'[{rule.metric.upper()} ALERT] {rule.notify_message}'
                for rule in triggered_alerts
            ]
        )

        for destination in destinations:
            factory = ALERT_DESTINATION_MAP.get(destination)
            if not factory:
                logger.error(
                    f'Unknown alert destination {destination}'
                )
                continue

            msg = factory(
                subject=subject,
                body=summary,
                fail_silently=settings.ALERT_FAIL_SILENTLY,
            )
            dispatcher.send(msg)

        for rule in triggered_alerts:
            # Make sure batch respects the cooldown.
            cache_key = f'alert_sent_{rule.id}'
            cache.set(
                cache_key, True, timeout=settings.ALERT_RATE_LIMIT_SECONDS
            )


def save_agent_ping_status(agent_ip, status_data):
    """
    Save agent ping status to database and log status change.
    """
    from monitoring.models import AgentPingStatus

    last_status = (
        AgentPingStatus.objects
        .filter(ip=agent_ip)
        .order_by('-timestamp')
        .first()
    )
    new_status = status_data.get('status', 'unreachable')
    agent_name = status_data.get('agent', 'unknown')
    uptime = status_data.get('uptime', -1)

    if last_status and last_status.status != new_status:
        logger.warning(
            f'Agent {agent_ip} status changed from'
            f' {last_status.status} to {new_status}'
        )

    AgentPingStatus.objects.create(
        agent_name=agent_name,
        ip=agent_ip,
        timestamp=timezone.now(),
        uptime=uptime,
        status=new_status
    )


@shared_task
def check_agent_health(agent_ip, port=8081):
    """
    Task to check agent health via health endpoint.

    Parameters:
        agent_ip (str): agent's IP address
        port (int): agent's server port
    """
    try:
        url = f'http://{agent_ip}:{port}/health'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        save_agent_ping_status(agent_ip, data)

        logger.info(f'Agent health check: {data}')
        return data

    except RequestException as e:
        logger.error(f'Error while pinging agent {agent_ip}: {str(e)}')
        save_agent_ping_status(
            agent_ip,
            {'status': 'unreachable', 'agent': 'unknown', 'uptime': -1}
        )
        raise

    except Exception as e:
        logger.error(
            f'Unexpected error while pinging agent {agent_ip}: {str(e)}'
        )
        save_agent_ping_status(
            agent_ip, {'status': 'error', 'agent': 'unknown', 'uptime': -1}
        )
        return {'status': 'error', 'unexpected_error': str(e)}


@shared_task
def check_all_agents_health(agent_ips, port=8081):
    """
    Task to check health of multiple agents.
    """
    task_group = group(check_agent_health.s(ip, port) for ip in agent_ips)
    result = task_group.apply_async()
    return result.id
