from rest_framework import serializers
from .models import ServerStatus


class ServerStatusResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerStatus
        fields = '__all__'


class ServerStatusRequestSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=100)
    ip = serializers.IPAddressField()
    server_name = serializers.CharField(max_length=50)

