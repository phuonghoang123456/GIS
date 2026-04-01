from django.urls import path

from .views import CurrentUserView, LoginView, LogoutView, RegisterView


urlpatterns = [
    path("register", RegisterView.as_view()),
    path("login", LoginView.as_view()),
    path("logout", LogoutView.as_view()),
    path("me", CurrentUserView.as_view()),
]
