from django.urls import path

from apps.api.views import health

urlpatterns = [
    path("health", health, name="health"),
]
