from rest_framework import serializers

from .models import CommandHistory


class CommandHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = CommandHistory
        fields = '__all__'
        read_only_fields = ('status', 'result', 'timestamp')

    def validate_command(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError('Command cannot be empty.')
        return value
