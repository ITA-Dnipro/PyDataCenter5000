from monitoring.services.prediction import PredictionService
from rest_framework import serializers

from .models import AgentMetric, CommandHistory, ServerStatus, TriggeredAlert


class AgentMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for AgentMetric.
    Exposes a single metric record
    (timestamp + resource usages).
    """
    class Meta:
        model = AgentMetric
        fields = (
            'id',
            'timestamp',
            'cpu',
            'ram',
            'disk',
            'load_avg',
            'nginx_down_count',
            'uptime',
            'server_status'
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

    forecasted_cpu = serializers.FloatField(write_only=True, required=False)
    anomaly_detected = serializers.BooleanField(
        write_only=True, required=False
    )

    class Meta:
        model = ServerStatus
        fields = [
            'id', 'hostname', 'ip', 'uptime', 'timestamp',
            'os', 'healthy', 'server_name', 'created_at',
            'prediction_flag', 'metrics',
            'forecasted_cpu', 'anomaly_detected',  # write-only
        ]
        read_only_fields = (
            'id', 'created_at', 'metrics', 'prediction_flag',
        )

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

    def update(self, instance, validated_data):
        forecasted_cpu = validated_data.pop('forecasted_cpu', None)
        anomaly_detected = validated_data.pop('anomaly_detected', False)

        instance = super().update(instance, validated_data)

        if forecasted_cpu is not None:
            service = PredictionService()
            new_flag = service.evaluate_flag(
                server_status=instance,
                forecasted_cpu=forecasted_cpu,
                anomaly_detected=anomaly_detected
            )
            instance.prediction_flag = new_flag
            instance.save(update_fields=['prediction_flag'])

        return instance


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
