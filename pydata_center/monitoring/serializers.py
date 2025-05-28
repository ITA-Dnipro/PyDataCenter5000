from rest_framework import serializers
from .models import CommandHistory

class CommandHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandHistory
        fields = '__all__'
        read_only_fields = ('status', 'result', 'timestamp')