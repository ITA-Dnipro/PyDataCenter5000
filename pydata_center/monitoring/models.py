from django.db import models


class ServerStatus(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['hostname', 'timestamp']),
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


class CommandHistory(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    hostname = models.CharField(max_length=100)
    command = models.TextField()
    result = models.JSONField(null=True, blank=True) #or TextField
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.hostname} - {self.status} - {self.timestamp}"