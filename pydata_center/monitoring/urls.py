from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CommandHistoryViewSet

app_name = 'monitoring'

router = DefaultRouter()
router.register(r'commands', CommandHistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
