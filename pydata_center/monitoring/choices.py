from django.db import models


class PredictionFlag(models.TextChoices):
    AT_RISK = 'At Risk', 'At Risk'
    ANOMALOUS = 'Anomalous', 'Anomalous'
    NO_HEARTBEAT = 'No Heartbeat', 'No Heartbeat'
