import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import OuterRef, Subquery
from django.utils.timezone import now

from .models import AgentUpgradeHistory, CommandHistory, ServerStatus

FILTERABLE_FIELDS = {'hostname', 'ip'}


def get_latest_agents(query_params=None, cutoff_seconds=60):
    cutoff_time = now() - timedelta(seconds=cutoff_seconds)

    filters = {}
    if query_params:
        for key, value in query_params.items():
            cleaned_value = value.strip()

            if not cleaned_value:
                continue

            if key.startswith('tag_'):
                filters[f'tags__{key[4:]}__icontains'] = cleaned_value
            elif key in FILTERABLE_FIELDS:
                filters[f'{key}__icontains'] = cleaned_value
            elif key == 'healthy' and cleaned_value in {'true', 'false'}:
                filters['healthy'] = (cleaned_value == 'true')
            elif key == 'status' and cleaned_value in {'online', 'offline'}:
                filters[
                    'timestamp__gte'
                    if cleaned_value == 'online'
                    else 'timestamp__lt'
                ] = cutoff_time

    latest_subquery = ServerStatus.objects.filter(
        hostname=OuterRef('hostname')
    ).order_by('-timestamp').values('pk')[:1]

    latest_statuses = ServerStatus.objects.filter(
        pk=Subquery(latest_subquery),
        **filters
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


logger = logging.getLogger(__name__)


def maybe_dispatch_upgrade(hostname: str, agent_version: str):
    latest_version = settings.LATEST_AGENT_VERSION

    if not agent_version:
        logger.warning(f'Agent {hostname} did not report version.')
        return

    if agent_version < latest_version:
        logger.info(
            f'Agent {hostname} outdated: {agent_version} < {latest_version}'
        )

        # create an update command
        CommandHistory.objects.create(
            hostname=hostname,
            type='agent',
            params={
                'action': 'upgrade',
                'target': latest_version,
                'url': settings.AGENT_PACKAGE_URL,
                'sha256': settings.AGENT_PACKAGE_SHA256,
            },
            status='pending'
        )

        # record in history
        AgentUpgradeHistory.objects.create(
            hostname=hostname,
            from_version=agent_version,
            to_version=latest_version,
            status='pending'
        )
