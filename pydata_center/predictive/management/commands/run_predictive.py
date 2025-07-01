from django.core.management.base import BaseCommand
from monitoring.models import PredictionFlag
from predictive.anomalies import is_heartbeat_missing
from predictive.database import get_all_server_metrics, mark_status
from predictive.inference import detect_anomaly, forecast_cpu
from predictive.logger import setup_logger

logger = setup_logger()

CPU_THRESHOLD = 90.0
WINDOW_SIZE = 5
METRIC_KEYS = [
    'cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime'
]


class Command(BaseCommand):
    """
    Management command that runs the full predictive health pipeline.

    Steps for each server:
      1. Build feature vector from last 5 readings of all metrics.
      2. Forecast CPU usage using the trained regression model.
      3. Detect anomalies via the IsolationForest model.
      4. Check for missing heartbeats.
      5. Update ServerStatus.prediction_flag accordingly.
    """
    help = 'Execute predictive health checks for all servers.'

    def handle(self, *args, **options):
        """
        Entry point for the command.
        """
        servers = get_all_server_metrics()
        checked = 0
        flagged = 0

        for s in servers:
            server_id = s['id']

            metric_data = {
                key: s.get(key, [])[-WINDOW_SIZE:] for key in METRIC_KEYS
            }

            if all(
                len(values) == WINDOW_SIZE for values in metric_data.values()
            ):
                checked += 1
                features = [
                    value
                    for window_tuple in zip(
                        *[metric_data[k] for k in METRIC_KEYS]
                    )
                    for value in window_tuple
                ]

                # Forecast CPU
                prediction = forecast_cpu(features)
                if prediction > CPU_THRESHOLD:
                    mark_status(server_id, PredictionFlag.AT_RISK)
                    logger.info(
                        f'Server {server_id}:'
                        f'forecasted high CPU load ({prediction:.1f}%)'
                    )
                    flagged += 1

                # Multivariate Anomaly Detection
                if detect_anomaly(features):
                    mark_status(server_id, PredictionFlag.ANOMALOUS)
                    logger.info(
                        f'Server {server_id}: anomaly detected on last window'
                    )
                    flagged += 1

            # Heartbeat Missing Check
            last_hb = s.get('last_heartbeat')
            if is_heartbeat_missing(last_hb):
                mark_status(server_id, PredictionFlag.NO_HEARTBEAT)
                logger.info(f'Server {server_id}: missing heartbeat')
                flagged += 1

        logger.info(
            f'Checked {checked} servers, flagged {flagged} total issues. '
        )
