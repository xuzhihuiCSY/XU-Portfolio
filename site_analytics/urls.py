from django.urls import path
from .views import analytics_data

urlpatterns = [
    path("data/", analytics_data, name="analytics_data"),
]
