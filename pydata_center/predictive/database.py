from django.db.models import Prefetch
from monitoring.models import AgentMetric, ServerStatus


def get_all_server_metrics(window: int = 5):
    """
    Fetch the latest `window` metrics for each server, plus its last heartbeat.

    Returns:
        List[dict]: each dict contains:
          - 'id': ServerStatus.pk
          - 'cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime':
              lists of length <= window, oldest→newest
          - 'last_heartbeat': timestamp from ServerStatus.timestamp
    """
    data = []

    servers = ServerStatus.objects.prefetch_related(
        Prefetch(
            'metrics',
            queryset=AgentMetric.objects.order_by('-timestamp'),
            to_attr='cached_metrics'
        )
    )

    for srv in servers:
        metrics = srv.cached_metrics[:window][::-1]

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


def mark_status(server_id: int, status: str):
    """
    Update the prediction_flag on a ServerStatus record.

    Args:
        server_id (int): primary key
        of the ServerStatus to update.
        status (str): new value for prediction_flag
        ('At Risk', 'Anomalous', etc.).
    """
    valid_choices = dict(
        ServerStatus._meta.get_field('prediction_flag').choices
    )
    if status not in valid_choices:
        raise ValueError(f'Invalid prediction_flag: {status}')

    srv = ServerStatus.objects.get(id=server_id)
    srv.prediction_flag = status
    srv.save(update_fields=['prediction_flag'])
