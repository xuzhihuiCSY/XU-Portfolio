from django.urls import path
from .views import labor_data

urlpatterns = [
    path("data/", labor_data, name="labor_data"),
]
