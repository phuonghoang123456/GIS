from django.urls import path

from .views import GeeFetchAllView, GeeFetchRainfallView, GeeFetchTemperatureView, GeeFetchView, GeeStatusView


urlpatterns = [
    path("status", GeeStatusView.as_view()),
    path("fetch", GeeFetchView.as_view()),
    path("fetch-rainfall", GeeFetchRainfallView.as_view()),
    path("fetch-temperature", GeeFetchTemperatureView.as_view()),
    path("fetch-all", GeeFetchAllView.as_view()),
]
