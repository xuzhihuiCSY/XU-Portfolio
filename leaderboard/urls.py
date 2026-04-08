from django.urls import path

from .views import (
    leaderboard_overview,
    leaderboard_player_status,
    leaderboard_players_by_value,
    leaderboard_submit,
)


urlpatterns = [
    path("", leaderboard_overview, name="leaderboard_overview"),
    path("submit/", leaderboard_submit, name="leaderboard_submit"),
    path("player/<str:player_id>/status/", leaderboard_player_status, name="leaderboard_player_status"),
    path("<str:board_type>/<int:value>/players/", leaderboard_players_by_value, name="leaderboard_players_by_value"),
]
