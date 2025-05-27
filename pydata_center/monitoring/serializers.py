from rest_framework import serializers

from .models import ServerStatus


class ServerStatusResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerStatus
        fields = '__all__'

    def create(self, validated_data):
        return ServerStatus.objects.create(**validated_data)


class ServerStatusRequestSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=100)
    server_name = serializers.CharField(max_length=50)
