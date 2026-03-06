from django.urls import path
from . import views

urlpatterns = [
    path("", views.stocks_page, name="stocks_page"),
    path("data/<str:symbol>/", views.stock_data, name="stock_data"),
]
