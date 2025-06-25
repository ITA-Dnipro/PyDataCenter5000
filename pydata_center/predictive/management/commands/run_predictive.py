import os

import django
from django.core.management.base import BaseCommand
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

        for s in servers:
            server_id = s['id']

            cpu_list = s.get('cpu', [])[-window:]
            ram_list = s.get('ram', [])[-window:]
            disk_list = s.get('disk', [])[-window:]
            load_list = s.get('load_avg', [])[-window:]
            nginx_list = s.get('nginx_down_count', [])[-window:]
            uptime_list = s.get('uptime', [])[-window:]

            if (
                len(cpu_list) == window and
                len(ram_list) == window and
                len(disk_list) == window and
                len(load_list) == window and
                len(nginx_list) == window and
                len(uptime_list) == window
            ):
                # Build flattened feature vector
                features = []
                for i in range(window):
                    features.extend([
                        cpu_list[i],
                        ram_list[i],
                        disk_list[i],
                        load_list[i],
                        nginx_list[i],
                        uptime_list[i],
                    ])

                # 1) Forecast CPU
                prediction = forecast_cpu(features)
                if prediction > 90:
                    mark_status(server_id, 'At Risk')
                    logger.info(
                        f'Server {server_id}: forecasted high CPU load'
                        f'({prediction:.1f}%)'
                    )

                # 2) Multivariate Anomaly Detection
                if detect_anomaly(features):
                    mark_status(server_id, 'Anomalous')
                    logger.info(
                        f'Server {server_id}: anomaly detected on last window'
                    )

            # 3) Heartbeat Missing Check
            last_hb = s.get('last_heartbeat')
            if is_heartbeat_missing(last_hb):
                mark_status(server_id, 'No Heartbeat')
                logger.info(f'Server {server_id}: missing heartbeat')
