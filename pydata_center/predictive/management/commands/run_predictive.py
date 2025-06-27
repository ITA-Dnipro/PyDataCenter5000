import os

import django
from django.core.management.base import BaseCommand
from monitoring.models import PredictionFlag
from predictive.anomalies import is_heartbeat_missing
from predictive.database import get_all_server_metrics, mark_status
from predictive.inference import detect_anomaly, forecast_cpu
from predictive.logger import setup_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pydata_center.settings')
django.setup()

logger = setup_logger()


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
        window = 5
        servers = get_all_server_metrics()

        metric_keys = [
            'cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime'
        ]

        for s in servers:
            server_id = s['id']

            metrics = {
                key: s.get(key, [])[-window:] for key in metric_keys
            }

            if all(len(lst) == window for lst in metrics.values()):

                # Build flattened feature vector
                features = []
                for i in range(window):
                    features.extend([metrics[key][i] for key in metric_keys])

                # 1) Forecast CPU
                prediction = forecast_cpu(features)
                if prediction > 90:
                    mark_status(server_id, PredictionFlag.AT_RISK)
                    logger.info(
                        f'Server {server_id}: forecasted high CPU load'
                        f'({prediction:.1f}%)'
                    )

                # 2) Multivariate Anomaly Detection
                if detect_anomaly(features):
                    mark_status(server_id, PredictionFlag.ANOMALOUS)
                    logger.info(
                        f'Server {server_id}: anomaly detected on last window'
                    )

            # 3) Heartbeat Missing Check
            last_hb = s.get('last_heartbeat')
            if is_heartbeat_missing(last_hb):
                mark_status(server_id, PredictionFlag.NO_HEARTBEAT)
                logger.info(f'Server {server_id}: missing heartbeat')
