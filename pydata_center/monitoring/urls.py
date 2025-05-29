from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CommandHistoryViewSet, receive_status

app_name = 'monitoring'

router = DefaultRouter()
router.register(r'commands', CommandHistoryViewSet)
urlpatterns = [
    path('status/', receive_status, name='receive_status'),
    path('', include(router.urls)),
]
