from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ServerStatus(models.Model):

    class Meta:
        indexes = [
            models.Index(fields=['hostname', 'timestamp'])
        ]
        verbose_name = 'server status'
        verbose_name_plural = 'server statuses'

    hostname = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    uptime = models.FloatField()
    timestamp = models.DateTimeField()
    os = models.CharField(max_length=50)
    healthy = models.BooleanField(default=False)
    server_name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.JSONField(null=True, blank=True, default=dict)

    def __str__(self):
        return f'{self.hostname} - {self.timestamp}'


class AgentMetric(models.Model):
    """Server metric collected by the agent."""

    class Meta:
        indexes = [
            models.Index(fields=['server_status', 'timestamp']),
        ]

    cpu = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    ram = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    disk = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    load_avg = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    nginx_down_count = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    uptime = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    server_status = models.ForeignKey(
        ServerStatus, on_delete=models.CASCADE, related_name='server_status'
    )

    def __str__(self):
        return f'Metrics for {self.server_status.hostname} at {self.timestamp}'


class CommandHistory(models.Model):
    COMMAND_TYPE_CHOICES = [
        ('linux', 'Linux Command'),
        ('agent', 'Agent Command'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    hostname = models.CharField(max_length=100, db_index=True)

    type = models.CharField(
        max_length=20, choices=COMMAND_TYPE_CHOICES, default='linux'
    )
    params = models.JSONField(null=True)

    result = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notify_on_success = models.BooleanField(
        default=False,
        help_text='If true, send a Discord alert upon successful completion.'
    )

    class Meta:
        verbose_name = 'command history'
        verbose_name_plural = 'command histories'

    def __str__(self):
        return f'{self.hostname} - {self.status} - {self.timestamp}'

    def clean(self):
        super().clean()

        # Validate command's params depending on its type
        if 'linux' in self.type:
            required = {'shell'}

            if not required.issubset(self.params):
                raise ValidationError({
                    'params': f'{self.type} command required keys: {required}'
                })


class AlertRule(models.Model):
    """
    Rule for triggering alerts based on server metrics evaluated by the
    agent. Alerts are triggered when rule's condition is met within a
    specified time window.
    """

    class Meta:
        verbose_name = 'alert rule'
        verbose_name_plural = 'alert rules'
        indexes = [models.Index(fields=['metric', 'is_active', 'hostname'])]

    METRIC_CHOICES = [
        ('cpu', 'CPU Usage'),
        ('ram', 'RAM Usage'),
        ('disk', 'Disk Usage'),
        ('load_avg', 'Average Load'),
        ('nginx_down_count', 'Nginx Failure Count'),
        ('uptime', 'Uptime'),
    ]
    OPERATOR_CHOICES = [
        ('>', 'Greater than'),
        ('<', 'Less than'),
        ('==', 'Equal to'),
        ('!=', 'Not equal to'),
    ]

    metric = models.CharField(max_length=32, choices=METRIC_CHOICES)
    operator = models.CharField(max_length=2, choices=OPERATOR_CHOICES)
    threshold = models.FloatField(validators=[MinValueValidator(0)])
    time_window_minutes = models.IntegerField(
        default=5, validators=[MinValueValidator(0)]
    )
    frequency = models.IntegerField(
        help_text='Check system every N minutes',
        default=5,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)

    notify_message = models.CharField(
        max_length=255, default='Alert triggered!'
    )

    hostname = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f'{self.metric} {self.operator} {self.threshold} '
            f'over {self.time_window_minutes}m'
        )


class TriggeredAlert(models.Model):
    """Alert triggered based on specific alert rule."""

    class Meta:
        verbose_name = 'triggered alert'
        verbose_name_plural = 'triggered alerts'
        indexes = [
            models.Index(fields=['rule', 'triggered_at']),
        ]

    rule = models.ForeignKey(
        AlertRule, on_delete=models.CASCADE, related_name='alert_rule'
    )
    message = models.CharField(max_length=255)
    triggered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f'{self.rule} triggered at {self.triggered_at} '
            f'with message {self.message}'
        )


class Webhook(models.Model):
    url = models.URLField()
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Webhook: {self.description or self.url[:30]}'


class AgentPingStatus(models.Model):
    """Agent ping status result from http request."""
    class Meta:
        indexes = [
            models.Index(fields=['agent_name', 'timestamp']),
        ]
        ordering = ['-timestamp']
        verbose_name = 'agent ping status'
        verbose_name_plural = 'agent ping statuses'

    STATUS_CHOICES = [
        ('ok', 'OK'),
        ('unreachable', 'Unreachable'),
        ('error', 'Error'),
    ]
    agent_name = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    timestamp = models.DateTimeField()
    uptime = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    def __str__(self):
        return f'{self.agent_name} - {self.timestamp} - {self.status}'


class AgentLogEntry(models.Model):
    """Log entry from the agent."""
    LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    agent_name = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    message = models.TextField()
    context = models.JSONField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['agent_name', 'timestamp']),
        ]
        ordering = ['-timestamp']
        verbose_name = 'agent log entry'
        verbose_name_plural = 'agent log entries'

    def __str__(self):
        return (
            f'[{self.timestamp}] {self.level} '
            f'{self.agent_name} - {self.message[:50]}'
        )
