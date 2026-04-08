from django.urls import path
from .views import home, privacy

urlpatterns = [
    path("", home, name="home"),
    path("contact/", home, name="contact"),
    path("privacy/", privacy, name="privacy"),
]
