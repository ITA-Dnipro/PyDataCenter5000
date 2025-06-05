from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (CommandHistoryViewSet, dashboard_view,
                    fetch_pending_command, receive_status,
                    submit_command_result)

app_name = 'monitoring'

router = DefaultRouter()
router.register(r'commands', CommandHistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('server/status/', receive_status, name='receive_status'),
    path(
        'command/fetch/',
        fetch_pending_command,
        name='fetch_pending_command'
    ),
    path(
        'command/result/',
        submit_command_result,
        name='submit_command_result'
    ),
    path(
        'dashboard/',
        dashboard_view,
        name='dashboard'
    ),
]
