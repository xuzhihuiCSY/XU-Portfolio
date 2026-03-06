from django.urls import path
from . import views

urlpatterns = [
    path("ping", views.ping, name="monitor_ping"),
    path("download", views.download_blob, name="monitor_download"),
]
