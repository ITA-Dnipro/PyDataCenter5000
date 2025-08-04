from datetime import datetime
from typing import Optional

from monitoring.models import PredictionFlag, ServerStatus
from predictive.status_evaluator import StatusEvaluator


class PredictionService:
    def __init__(
        self,
        cpu_threshold: float = 85.0,
        alert_padding_sec: int = 30,
        heartbeat_timeout_sec: int = 60,
    ):
        self.evaluator = StatusEvaluator(
            cpu_threshold=cpu_threshold,
            alert_padding_sec=alert_padding_sec,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
        )

    def evaluate_flag(
        self,
        server_status: ServerStatus,
        forecasted_cpu: float,
        anomaly_detected: bool
    ) -> Optional[str]:  # ← виправлено
        """
        Return the appropriate PredictionFlag value
        for a given server and metrics.
        """
        return self.evaluator.evaluate(
            server_id=server_status.id,
            forecasted_cpu=forecasted_cpu,
            anomaly_detected=anomaly_detected,
            last_seen_at=server_status.last_seen_at
        )
