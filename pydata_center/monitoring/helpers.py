from datetime import timedelta

from django.db.models import OuterRef, Subquery
from django.utils.timezone import now

from .models import ServerStatus


def get_latest_agents(cutoff_seconds=60):
    cutoff_time = now() - timedelta(seconds=cutoff_seconds)

    latest_subquery = ServerStatus.objects.filter(
        hostname=OuterRef('hostname')
    ).order_by('-timestamp').values('pk')[:1]

    latest_statuses = ServerStatus.objects.filter(
        pk=Subquery(latest_subquery)
    ).order_by('hostname')

    return [
        {
            'hostname': agent.hostname,
            'ip': agent.ip,
            'uptime': agent.uptime,
            'timestamp': agent.timestamp,
            'healthy': agent.healthy,
            'tags': agent.tags,
            'offline': agent.timestamp < cutoff_time,
        }
        for agent in latest_statuses
    ]
