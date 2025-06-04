from django.db import models


class ServerStatus(models.Model):

    class Meta:
        indexes = [
            models.Index(fields=['hostname', 'timestamp']),
        ]

    hostname = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    uptime = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    os = models.CharField(max_length=50)
    healthy = models.BooleanField(default=False)
    server_name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.hostname} - {self.timestamp}'


class AgentMetric(models.Model):
    cpu = models.FloatField(null=True, blank=True)
    ram = models.FloatField(null=True, blank=True)
    disk = models.FloatField(null=True, blank=True)
    load_avg = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    server_status = models.ForeignKey(
        ServerStatus, on_delete=models.CASCADE, related_name='server_status'
    )

    class Meta:
        indexes = [
            models.Index(fields=['server_status', 'timestamp']),
        ]

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
