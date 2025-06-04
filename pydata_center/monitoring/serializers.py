from rest_framework import serializers

from .models import CommandHistory, ServerStatus


class ServerStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerStatus
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

    def validate_hostname(self, value):
        if ' ' in value:
            raise serializers.ValidationError(
                'Hostname cannot contain spaces.'
            )
        return value

    def validate_server_name(self, value):
        if not value.isidentifier():
            raise serializers.ValidationError('Invalid server name format.')
        return value


class CommandHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandHistory
        fields = '__all__'
        read_only_fields = ('status', 'result', 'timestamp')

    def validate_command(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError('Command cannot be empty.')
        return value
