import json
import random
from uuid import UUID

from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import LeaderboardEntry

BOARD_TYPES = [
    LeaderboardEntry.BOARD_SCORE,
    LeaderboardEntry.BOARD_LENGTH,
    LeaderboardEntry.BOARD_BEST_COMBO,
]


def _top_values(board_type: str, limit: int = 5) -> list[int]:
    return list(
        LeaderboardEntry.objects.filter(board_type=board_type)
        .values_list("value", flat=True)
        .distinct()
        .order_by("-value")[:limit]
    )


def _prune_board(board_type: str) -> None:
    keep_values = _top_values(board_type, limit=5)
    if not keep_values:
        return

    LeaderboardEntry.objects.filter(board_type=board_type).exclude(value__in=keep_values).delete()


def _board_summary(board_type: str, preferred_player_id: UUID | None = None) -> dict:
    groups = list(
        LeaderboardEntry.objects.filter(board_type=board_type)
        .values("value")
        .annotate(total_players=Count("id"))
        .order_by("-value")[:5]
    )

    entries = []
    for idx, group in enumerate(groups, start=1):
        value = group["value"]
        same_value_qs = LeaderboardEntry.objects.filter(board_type=board_type, value=value)

        preferred_name = None
        is_self = False
        if preferred_player_id is not None:
            preferred_name = (
                same_value_qs.filter(player_id=preferred_player_id)
                .values_list("player_name", flat=True)
                .first()
            )

        if preferred_name:
            display_name = preferred_name
            is_self = True
        else:
            names = list(same_value_qs.values_list("player_name", flat=True))
            display_name = random.choice(names) if names else ""

        total_players = int(group["total_players"])
        entries.append({
            "rank": idx,
            "value": value,
            "display_name": display_name,
            "is_self": is_self,
            "total_players": total_players,
            "extra_count": max(total_players - 1, 0),
        })

    board_min = entries[-1]["value"] if entries else None
    return {
        "count_groups": len(entries),
        "min": board_min,
        "entries": entries,
    }


def _try_parse_uuid(value: str):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _process_single_board(board_type: str, player_id: UUID, player_name: str, new_value: int) -> bool:
    now = timezone.now()

    with transaction.atomic():
        existing = (
            LeaderboardEntry.objects.select_for_update()
            .filter(board_type=board_type, player_id=player_id)
            .first()
        )

        if existing is not None:
            if new_value > existing.value:
                existing.value = new_value
                existing.player_name = player_name
                existing.achieved_at = now
                existing.save(update_fields=["value", "player_name", "achieved_at"])
                _prune_board(board_type)
                return True
            return False

        top_values = _top_values(board_type, limit=5)
        can_enter = False
        if len(top_values) < 5:
            can_enter = True
        else:
            threshold = top_values[-1]
            if new_value > threshold or new_value in top_values:
                can_enter = True

        if not can_enter:
            return False

        LeaderboardEntry.objects.create(
            board_type=board_type,
            player_id=player_id,
            player_name=player_name,
            value=new_value,
            achieved_at=now,
        )
        _prune_board(board_type)
        return True


def _player_status_for_board(board_type: str, player_uuid: UUID) -> dict:
    entry = (
        LeaderboardEntry.objects.filter(board_type=board_type, player_id=player_uuid)
        .order_by("achieved_at")
        .first()
    )
    if entry is None:
        return {
            "on_board": False,
            "value": None,
            "rank": None,
            "total_players": 0,
            "achieved_at": None,
        }

    top_values = _top_values(board_type, limit=5)
    rank = None
    if entry.value in top_values:
        rank = top_values.index(entry.value) + 1

    total_players = LeaderboardEntry.objects.filter(board_type=board_type, value=entry.value).count()
    return {
        "on_board": rank is not None,
        "value": entry.value,
        "rank": rank,
        "total_players": total_players,
        "achieved_at": entry.achieved_at.isoformat(),
    }


@require_GET
def leaderboard_overview(request):
    preferred_player_id = _try_parse_uuid(request.GET.get("player_id"))

    return JsonResponse({
        "score_board": _board_summary(LeaderboardEntry.BOARD_SCORE, preferred_player_id),
        "length_board": _board_summary(LeaderboardEntry.BOARD_LENGTH, preferred_player_id),
        "best_combo_board": _board_summary(LeaderboardEntry.BOARD_BEST_COMBO, preferred_player_id),
    })


@require_GET
def leaderboard_players_by_value(request, board_type: str, value: int):
    if board_type not in BOARD_TYPES:
        return JsonResponse({"error": "Invalid board_type."}, status=400)

    players_qs = LeaderboardEntry.objects.filter(board_type=board_type, value=value).order_by("achieved_at")
    players = [
        {
            "player_id": str(item.player_id),
            "player_id_suffix": str(item.player_id)[-4:],
            "player_name": item.player_name,
            "display_name": f"{item.player_name}#{str(item.player_id)[-4:]}",
            "value": item.value,
            "achieved_at": item.achieved_at.isoformat(),
        }
        for item in players_qs
    ]

    return JsonResponse({
        "board_type": board_type,
        "value": value,
        "total_players": len(players),
        "players": players,
    })


@require_GET
def leaderboard_player_status(request, player_id: str):
    player_uuid = _try_parse_uuid(player_id)
    if player_uuid is None:
        return JsonResponse({"error": "player_id must be a valid UUID."}, status=400)

    return JsonResponse({
        "player_id": str(player_uuid),
        "score": _player_status_for_board(LeaderboardEntry.BOARD_SCORE, player_uuid),
        "length": _player_status_for_board(LeaderboardEntry.BOARD_LENGTH, player_uuid),
        "best_combo": _player_status_for_board(LeaderboardEntry.BOARD_BEST_COMBO, player_uuid),
    })


@require_http_methods(["POST"])
@csrf_exempt
def leaderboard_submit(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    player_uuid = _try_parse_uuid(payload.get("player_id"))
    if player_uuid is None:
        return JsonResponse({"error": "player_id must be a valid UUID."}, status=400)

    player_name = str(payload.get("player_name", "")).strip()
    if not player_name:
        return JsonResponse({"error": "player_name is required."}, status=400)

    try:
        score = int(payload.get("score"))
        snake_length = int(payload.get("snake_length"))
        best_combo = int(payload.get("best_combo"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "score, snake_length, and best_combo must be integers."}, status=400)

    score_updated = _process_single_board(LeaderboardEntry.BOARD_SCORE, player_uuid, player_name, score)
    length_updated = _process_single_board(LeaderboardEntry.BOARD_LENGTH, player_uuid, player_name, snake_length)
    best_combo_updated = _process_single_board(LeaderboardEntry.BOARD_BEST_COMBO, player_uuid, player_name, best_combo)

    return JsonResponse({
        "score_updated": score_updated,
        "length_updated": length_updated,
        "best_combo_updated": best_combo_updated,
        "score_board": _board_summary(LeaderboardEntry.BOARD_SCORE, player_uuid),
        "length_board": _board_summary(LeaderboardEntry.BOARD_LENGTH, player_uuid),
        "best_combo_board": _board_summary(LeaderboardEntry.BOARD_BEST_COMBO, player_uuid),
    })
