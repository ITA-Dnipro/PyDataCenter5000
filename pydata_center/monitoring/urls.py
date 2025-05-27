from django.urls import path

from .views import receive_status

app_name = 'monitoring'

urlpatterns = [
    path('status/', receive_status, name='receive_status'),
]
