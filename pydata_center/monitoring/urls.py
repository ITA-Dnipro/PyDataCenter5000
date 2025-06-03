from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (CommandHistoryViewSet, fetch_pending_command,
                    receive_status, submit_command_result)

app_name = 'monitoring'

router = DefaultRouter()
router.register(r'commands', CommandHistoryViewSet)
urlpatterns = [
    path('status/', receive_status, name='receive_status'),
    path('', include(router.urls)),
    path(
        'command/fetch/', fetch_pending_command, name='fetch_pending_command'
    ),
    path(
        'command/result/',
        submit_command_result,
        name='submit_command_result'
    )
]
