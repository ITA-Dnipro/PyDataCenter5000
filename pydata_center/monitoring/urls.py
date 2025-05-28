from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CommandHistoryViewSet, create_command, fetch_pending_command, submit_command_result

app_name = 'monitoring'

router = DefaultRouter()
router.register(r'commands', CommandHistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('command/', create_command, name='create_command'),
    path('command/fetch/', fetch_pending_command, name='fetch_pending_command'),
    path('api/command/result/', submit_command_result, name='submit_command_result'),
]
