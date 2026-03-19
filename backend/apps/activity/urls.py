from django.urls import path

from .views import ActivityHistoryView, ActivityStatsView, LogActivityView


urlpatterns = [
    path("log", LogActivityView.as_view()),
    path("history", ActivityHistoryView.as_view()),
    path("stats", ActivityStatsView.as_view()),
]
