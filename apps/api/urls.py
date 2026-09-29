"""URL configuration for API v1."""

from django.urls import path

from apps.api.views import health, route_map_view, route_view

urlpatterns = [
    path("health", health, name="health"),
    path("route", route_view, name="route"),
    path("route/map", route_map_view, name="route-map"),
]
