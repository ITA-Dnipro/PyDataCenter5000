from datetime import datetime
from typing import Optional

import numpy as np
from django.utils import timezone


def is_latency_anomalous(
    latency_series: np.ndarray,
    threshold: float = 2.5
) -> bool:
    """
    Determine whether the most recent latency value
    is an outlier based on a Z-score threshold.
    """
    if latency_series.size < 2:
        return False

    mean = np.mean(latency_series)
    std = np.std(latency_series)
    if std == 0:
        return False

    latest = latency_series[-1]
    z_score = (latest - mean) / std
    return abs(z_score) > threshold


def is_heartbeat_missing(
    last_heartbeat: Optional[datetime],
    timeout: int = 60
) -> bool:
    """
    Check if the heartbeat timestamp is older than a timeout.
    """
    # No heartbeat at all, so treat as missing
    if not last_heartbeat:
        return True

    # Ensure both are timezone-aware
    now = timezone.now()

    # If last_heartbeat is naive, assume UTC
    if timezone.is_naive(last_heartbeat):
        last_heartbeat = timezone.make_aware(last_heartbeat, timezone.utc)

    return (now - last_heartbeat).total_seconds() > timeout
