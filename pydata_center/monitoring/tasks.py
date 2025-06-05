import logging
import operator
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from pydata_center.monitoring.models import AgentMetric, AlertRule

logger = logging.getLogger(__name__)

OPERATOR_MAP = {
    '>': operator.gt,
    '<': operator.lt,
    '==': operator.eq,
    '!=': operator.ne,
}


@shared_task
def evaluate_agent_alerts():
    """Task to evaluate alert rules and trigger notification."""
    rules = AlertRule.objects.filter(is_active=True)

    for rule in rules:
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
            logger.debug(f'No data for rule: {rule}')

            continue

        avg = sum(values) / len(values)

        triggered = OPERATOR_MAP[rule.operator](avg, rule.threshold)

        if triggered:
            logger.warning(f'Alert triggered for rule: {rule}')
            logger.warning(f'Alert message: {rule.notify_message}')
        else:
            logger.debug(f'No alerts triggered since {time_window_start}')
