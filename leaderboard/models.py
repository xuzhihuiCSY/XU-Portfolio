import uuid

from django.db import models


class LeaderboardEntry(models.Model):
    BOARD_SCORE = "score"
    BOARD_LENGTH = "length"
    BOARD_BEST_COMBO = "best_combo"

    BOARD_TYPE_CHOICES = [
        (BOARD_SCORE, "Score"),
        (BOARD_LENGTH, "Length"),
        (BOARD_BEST_COMBO, "Best Combo"),
    ]

    board_type = models.CharField(max_length=20, choices=BOARD_TYPE_CHOICES)
    player_id = models.UUIDField(default=uuid.uuid4)
    player_name = models.CharField(max_length=64)
    value = models.IntegerField()
    achieved_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["board_type", "player_id"], name="uniq_board_player"),
        ]
        indexes = [
            models.Index(fields=["board_type", "-value", "achieved_at"], name="idx_lb_board_val_time"),
        ]

    def __str__(self):
        return f"{self.board_type}:{self.player_name}:{self.value}"
