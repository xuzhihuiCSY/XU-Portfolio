from django.contrib import admin

from .models import LeaderboardEntry


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("board_type", "value", "player_name", "player_id", "achieved_at")
    list_filter = ("board_type",)
    search_fields = ("player_name", "player_id")
    ordering = ("board_type", "-value", "achieved_at")
