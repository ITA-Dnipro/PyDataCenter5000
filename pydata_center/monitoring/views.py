from django.shortcuts import render
from .models import CommandHistory
from .serializers import CommandHistorySerializer
from rest_framework import viewsets

class CommandHistoryViewSet(viewsets.ModelViewSet):
    queryset = CommandHistory.objects.all()
    serializer_class = CommandHistorySerializer
