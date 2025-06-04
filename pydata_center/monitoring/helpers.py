from datetime import timedelta

from django.db.models import Max, Q
from django.utils.timezone import now

from .models import ServerStatus


def get_latest_agents(cutoff_seconds=60):
    cutoff_time = now() - timedelta(seconds=cutoff_seconds)

    latest = (
        ServerStatus.objects
        .values('hostname')
        .annotate(latest_ts=Max('timestamp'))
    )

    query = Q()
    for entry in latest:
        query |= Q(hostname=entry['hostname'], timestamp=entry['latest_ts'])

    latest_statuses = ServerStatus.objects.filter(query)

    return [
        {
            'hostname': agent.hostname,
            'ip': agent.ip,
            'uptime': agent.uptime,
            'timestamp': agent.timestamp,
            'healthy': agent.healthy,
            'offline': agent.timestamp < cutoff_time,
        }
        for agent in latest_statuses
    ]
