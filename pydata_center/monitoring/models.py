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
    servername = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.hostname} - {self.timestamp}"
