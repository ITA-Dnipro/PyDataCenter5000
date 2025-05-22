from django.db import models

class ServerStatus(models.Model):
    class Meta:
        indexes = [
        models.Index(fields=['hostname', 'timestamp']),
    ]
        
    hostname = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    uptime = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    os = models.CharField(max_length=50)
    healthy = models.BooleanField(default=False)
    service = models.CharField(max_length=50)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.hostname} - {self.timestamp}"
