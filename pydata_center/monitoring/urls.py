from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (CommandHistoryViewSet, TriggeredAlertViewSet,
                    create_agent_metric, dashboard_view, fetch_pending_command,
                    metrics_graphing_page, metrics_history_view,
                    receive_status, submit_command_result)

app_name = 'monitoring'

router = DefaultRouter()
router.register(r'commands', CommandHistoryViewSet)
router.register(r'triggered-alerts', TriggeredAlertViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('server/status/', receive_status, name='receive_status'),
    path(
        'command/fetch/',
        fetch_pending_command,
        name='fetch_pending_command'
    ),
    path(
        'command/result/<int:command_id>/',
        submit_command_result,
        name='submit_command_result'
    ),
    path(
        'dashboard/',
        dashboard_view,
        name='dashboard'
    ),
    path(
        'agent/metrics/',
        create_agent_metric,
        name='agent-metrics'
    ),
    path('metrics/history/', metrics_history_view, name='metrics_history'),
    path('metrics/graphic/', metrics_graphing_page, name='metrics_graphic'),
]
