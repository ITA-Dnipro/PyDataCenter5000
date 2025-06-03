from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (TokenObtainPairView,
                                            TokenRefreshView)

from .health import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT token endpoints
    path(
        f'{settings.API_PREFIX}/token/',
        TokenObtainPairView.as_view(),
        name='token_obtain_pair'
    ),
    path(
        f'{settings.API_PREFIX}/token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh'
    ),

    path(
        f'{settings.API_PREFIX}/',
        include('monitoring.urls', namespace='monitoring')
    ),
    path('health/', health_check, name='health_check'),
]
