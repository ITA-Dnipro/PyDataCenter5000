from django.db import models


class ServerStatus(models.Model):

    class Meta:
        indexes = [
            models.Index(fields=['hostname', 'timestamp'])
        ]

    hostname = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    uptime = models.FloatField()
    timestamp = models.DateTimeField()
    os = models.CharField(max_length=50)
    healthy = models.BooleanField(default=False)
    server_name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.hostname} - {self.timestamp}'


class AgentMetric(models.Model):

    class Meta:
        indexes = [
            models.Index(fields=['server_status', 'timestamp']),
        ]

    cpu = models.FloatField(null=True, blank=True)
    ram = models.FloatField(null=True, blank=True)
    disk = models.FloatField(null=True, blank=True)
    load_avg = models.FloatField(null=True, blank=True)
    nginx_down_count = models.IntegerField(null=True, blank=True)
    uptime = models.FloatField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    server_status = models.ForeignKey(
        ServerStatus, on_delete=models.CASCADE, related_name='server_status'
    )

    def __str__(self):
        return f'Metrics for {self.server_status.hostname} at {self.timestamp}'


class CommandHistory(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    hostname = models.CharField(max_length=100, db_index=True)
    command = models.TextField()
    result = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.hostname} - {self.status} - {self.timestamp}'


class AlertRule(models.Model):

    class Meta:
        indexes = [models.Index(fields=['metric', 'is_active'])]

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
    threshold = models.FloatField()
    time_window_minutes = models.IntegerField(default=5)
    frequency = models.IntegerField(
        help_text='Check system every N minutes', default=5
    )
    is_active = models.BooleanField(default=True)

    notify_message = models.CharField(
        max_length=255, default='Alert triggered!'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f'{self.metric} {self.operator} {self.threshold} '
            f'over {self.time_window_minutes}m'
        )
