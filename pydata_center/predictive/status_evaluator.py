from datetime import datetime, timedelta

from monitoring.models import PredictionFlag


class StatusEvaluator:
    """
    Encapsulates all business rules for setting ServerStatus.prediction_flag.
    """

    def __init__(
        self,
        cpu_threshold: float,
        alert_padding_sec: int = 30,
        heartbeat_timeout_sec: int = 60
    ):
        self.cpu_threshold = cpu_threshold
        self.alert_padding = timedelta(seconds=alert_padding_sec)
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout_sec)

    def evaluate(
        self,
        server_id: int,
        forecasted_cpu: float,
        anomaly_detected: bool,
        last_seen_at: datetime,
    ) -> str:
        """
        Return one of PredictionFlag values based on inputs.
        Order of precedence: heartbeat → CPU forecast → anomaly.

        Args:
            server_id: ID of the server
            forecasted_cpu: predicted CPU percentage
            anomaly_detected: whether IsolationForest flagged an anomaly
            last_seen_at: timestamp of last heartbeat

        Returns:
            A member of PredictionFlag.choices
        """
        now = datetime.utcnow()
        # 1. Heartbeat missing
        if not last_seen_at or (now - last_seen_at) > self.heartbeat_timeout:
            return PredictionFlag.NO_HEARTBEAT

        # 2. CPU over threshold
        if forecasted_cpu > self.cpu_threshold:
            return PredictionFlag.AT_RISK

        # 3. Anomaly detection
        if anomaly_detected:
            return PredictionFlag.ANOMALOUS

        # 4. All good
        return None
