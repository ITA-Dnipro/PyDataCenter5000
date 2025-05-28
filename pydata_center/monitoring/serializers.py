from rest_framework import serializers

from .models import ServerStatus


class ServerStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerStatus
        fields = '__all__'
