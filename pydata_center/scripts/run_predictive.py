from data.database import get_all_server_metrics, mark_status
from django.core.management.base import BaseCommand
from monitoring.models import PredictionFlag
from predictive.anomaly import detect_anomaly, is_heartbeat_missing
from predictive.forecasting import forecast_cpu

from pydata_center.utils.logger import setup_logger

logger = setup_logger()

CPU_THRESHOLD = 90.0
WINDOW_SIZE = 5
METRIC_KEYS = [
    'cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime'
]


def setup_predictive_pipeline():
    """
    Step 1: Load all server metric histories.
    """
    return get_all_server_metrics()


def run_forecasting(server_metrics: dict) -> bool:
    """
    Step 2: Forecast CPU load and return True if above threshold.
    """
    features = _extract_features(server_metrics)
    prediction = forecast_cpu(features)
    if prediction > CPU_THRESHOLD:
        logger.info(
            f"Server {server_metrics['id']}: "
            f'forecasted high CPU load ({prediction:.1f}%)'
        )
        return True
    return False


def detect_anomalies_step(server_metrics: dict) -> bool:
    """
    Step 3: Run the multivariate anomaly detector.
    """
    features = _extract_features(server_metrics)
    if detect_anomaly(features):
        logger.info(f"Server {server_metrics['id']}: anomaly detected")
        return True
    return False


def run_heartbeat_check(server_metrics: dict) -> bool:
    """
    Step 4: Check for missing heartbeat.
    """
    last_hb = server_metrics.get('last_heartbeat')
    if is_heartbeat_missing(last_hb):
        logger.info(f"Server {server_metrics['id']}: missing heartbeat")
        return True
    return False


def _extract_features(server_metrics: dict) -> list:
    """
    Peel off the last WINDOW_SIZE readings of each metric,
    flatten into a single feature vector.
    """
    metric_data = {
        key: server_metrics.get(key, [])[-WINDOW_SIZE:]
        for key in METRIC_KEYS
    }
    # if any series is too short, we return an empty list
    if any(len(v) < WINDOW_SIZE for v in metric_data.values()):
        return []
    # interleave the per-metric windows
    return [
        val
        for window in zip(*(metric_data[k] for k in METRIC_KEYS))
        for val in window
    ]


class Command(BaseCommand):
    help = 'Execute predictive health checks for all servers.'

    def handle(self, *args, **options):
        servers = setup_predictive_pipeline()
        checked = 0
        flagged = 0

        for s in servers:
            server_id = s['id']
            checked += 1

            # Forecasting
            if run_forecasting(s):
                mark_status(server_id, PredictionFlag.AT_RISK)
                flagged += 1

            # Anomaly detection
            if detect_anomalies_step(s):
                mark_status(server_id, PredictionFlag.ANOMALOUS)
                flagged += 1

            # Heartbeat check
            if run_heartbeat_check(s):
                mark_status(server_id, PredictionFlag.NO_HEARTBEAT)
                flagged += 1

        logger.info(
            f'Checked {checked} servers, flagged {flagged} total issues.'
        )
