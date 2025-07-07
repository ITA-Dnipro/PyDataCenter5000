from rest_framework import serializers

from .models import AgentMetric, CommandHistory, ServerStatus, TriggeredAlert


class AgentMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentMetric
        fields = (
            'id',
            'timestamp',
            'cpu',
            'ram',
            'disk',
            'load_avg',
            'server_status',
        )
        read_only_fields = ('id', 'timestamp')

    def validate_cpu(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('CPU usage must be 0–100%.')
        return value

    def validate_ram(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('RAM usage must be 0–100%.')
        return value

    def validate_disk(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('Disk usage must be 0–100%.')
        return value

    def validate_load_avg(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Load average must be ≥ 0.')
        return value


class ServerStatusSerializer(serializers.ModelSerializer):
    metrics = AgentMetricSerializer(many=True, read_only=True)
    tags = serializers.JSONField(required=False)

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

    def validate_tags(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Invalid data. Expected a dictionary object.'
            )
        return value


class CommandHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandHistory
        fields = '__all__'
        read_only_fields = ('timestamp',)

    def validate_command(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError('Command cannot be empty.')
        return value


class TriggeredAlertSerializer(serializers.ModelSerializer):

    class Meta:
        model = TriggeredAlert
        fields = '__all__'


class AgentRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
