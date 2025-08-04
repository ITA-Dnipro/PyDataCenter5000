import logging

from django.db.models import Prefetch
from monitoring.models import AgentMetric, ServerStatus

logger = logging.getLogger(__name__)


class MetricRepository:
    def __init__(self, window: int = 5):
        self.window = window

    def fetch_metrics(self):
        """
        Fetch the latest `window` metrics for
        each server, plus its last heartbeat.
        """
        servers = ServerStatus.objects.prefetch_related(
            Prefetch(
                'metrics',
                queryset=AgentMetric.objects.order_by('-timestamp'),
                to_attr='cached_metrics'
            )
        )

        data = []
        for srv in servers:
            metrics = srv.cached_metrics[:self.window][::-1]
            data.append({
                'id': srv.id,
                'cpu': [m.cpu for m in metrics],
                'ram': [m.ram for m in metrics],
                'disk': [m.disk for m in metrics],
                'load_avg': [m.load_avg for m in metrics],
                'nginx_down_count': [m.nginx_down_count for m in metrics],
                'uptime': [m.uptime for m in metrics],
                'last_heartbeat': srv.timestamp,
            })

        return data

    def update_status(self, server_id: int, status: str):
        """
        Update the prediction_flag on a ServerStatus record.
        """
        valid_choices = dict(
            ServerStatus._meta.get_field('prediction_flag').choices
        )
        if status not in valid_choices:
            raise ValueError(f'Invalid prediction_flag: {status}')

        try:
            srv = ServerStatus.objects.get(id=server_id)
            srv.prediction_flag = status
            srv.save(update_fields=['prediction_flag'])
        except ServerStatus.DoesNotExist:
            logger.error(f'ServerStatus with id={server_id} not found.')
