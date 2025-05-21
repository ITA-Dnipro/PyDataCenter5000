from django.db import models

class ServerStatus(models.Model):
    hostname = models.Charfield(max_length=100)
    ip = models.GenericIPAddressField()
    uptime = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.hostname} - {self.timestamp}"
