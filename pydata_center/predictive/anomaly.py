import logging
from datetime import datetime
from typing import Optional

import numpy as np
from django.utils import timezone

logger = logging.getLogger(__name__)


class LatencyAnomalyDetector:
    def __init__(self, threshold: float = 2.5):
        self.threshold = threshold

    def detect(self, latency_series: np.ndarray) -> bool:
        """
        Determine whether the most recent latency value
        is an outlier based on a Z-score threshold.
        """
        latency_series = latency_series[~np.isnan(latency_series)]

        if latency_series.size < 2:
            logger.debug('Latency series too short to evaluate anomaly.')
            return False

        mean = np.mean(latency_series)
        std = np.std(latency_series)

        if std == 0:
            logger.debug('Latency series has zero std deviation.')
            return False

        latest = latency_series[-1]
        z_score = (latest - mean) / std

        is_anomaly = abs(z_score) > self.threshold
        logger.info(
            f'Z-score={z_score:.2f}, '
            f'threshold={self.threshold}, '
            f'anomaly={is_anomaly}'
        )
        return is_anomaly


def is_heartbeat_missing(
    last_heartbeat: Optional[datetime],
    timeout: int = 60
) -> bool:
    """
    Check if the heartbeat timestamp is older than a timeout.
    """
    if not last_heartbeat:
        return True

    now = timezone.now()

    if timezone.is_naive(last_heartbeat):
        last_heartbeat = timezone.make_aware(last_heartbeat, timezone.utc)

    return (now - last_heartbeat).total_seconds() > timeout
