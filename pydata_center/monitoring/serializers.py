from rest_framework import serializers

from .models import CommandHistory, ServerStatus


class ServerStatusResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerStatus
        fields = '__all__'

    def create(self, validated_data):
        return ServerStatus.objects.create(**validated_data)


class ServerStatusRequestSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=100)
    server_name = serializers.CharField(max_length=50)


class CommandHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandHistory
        fields = '__all__'
        read_only_fields = ('status', 'result', 'timestamp')

    def validate_command(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError('Command cannot be empty.')
        return value
