from datetime import timedelta

from django.utils.timezone import now

from .models import ServerStatus


def get_latest_agents(cutoff_seconds=60):
    cutoff_time = now() - timedelta(seconds=cutoff_seconds)

    latest_statuses = (
        ServerStatus.objects
        .order_by('hostname', '-timestamp')
        .distinct('hostname')
    )

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
