from rest_framework import serializers
from .models import CommandHistory

class CommandHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandHistory
        fields = '__all__'