from datetime import timedelta
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from .models import ClickEvent


def _date_range_days(end_date, days):
    # inclusive range of length `days` ending at end_date
    start = end_date - timedelta(days=days - 1)
    cur = start
    out = []
    while cur <= end_date:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _forecast_next_3(actual_counts):
    """
    Simple, stable forecast:
    - base = 7-day moving average
    - trend = avg(last 3) - avg(prev 3) (small)
    """
    if not actual_counts:
        return [0, 0, 0]

    series = actual_counts[:]
    last7 = series[-7:] if len(series) >= 7 else series
    base = sum(last7) / max(1, len(last7))

    if len(series) >= 6:
        a = sum(series[-3:]) / 3.0
        b = sum(series[-6:-3]) / 3.0
        trend = (a - b) * 0.5
    else:
        trend = 0.0

    preds = []
    val = base
    for _ in range(3):
        val = max(0.0, val + trend)
        preds.append(int(round(val)))
    return preds


def analytics_data(request):
    now = timezone.localtime()
    today = now.date()

    total = ClickEvent.objects.count()
    today_clicks = ClickEvent.objects.filter(created_at__date=today).count()

    # Last 21 days (daily)
    end = today
    days = _date_range_days(end, 21)

    qs_daily = (
        ClickEvent.objects
        .filter(created_at__date__gte=days[0], created_at__date__lte=end)
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(c=Count("id"))
        .order_by("d")
    )
    daily_map = {row["d"]: row["c"] for row in qs_daily}
    daily_counts = [int(daily_map.get(d, 0)) for d in days]
    daily_labels = [d.strftime("%Y-%m-%d") for d in days]

    preds = _forecast_next_3(daily_counts)
    forecast_labels = [(end + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 4)]

    # Device pie
    qs_dev = ClickEvent.objects.values("device_type").annotate(c=Count("id"))
    device_counts = {"mobile": 0, "computer": 0, "other": 0}
    for row in qs_dev:
        device_counts[row["device_type"]] = int(row["c"])

    # Heatmap: weekday x time-block (night/morning/afternoon/evening)
    # time blocks: 0=0-5, 1=6-11, 2=12-17, 3=18-23
    start_hm = end - timedelta(days=60)  # lookback window for “preference”
    events = ClickEvent.objects.filter(created_at__date__gte=start_hm, created_at__date__lte=end).values_list("created_at", flat=True)

    heat = [[0, 0, 0, 0] for _ in range(7)]  # weekday 0=Mon..6=Sun
    for dt in events:
        dt = timezone.localtime(dt)
        wd = dt.weekday()
        hr = dt.hour
        block = 0 if hr <= 5 else 1 if hr <= 11 else 2 if hr <= 17 else 3
        heat[wd][block] += 1

    return JsonResponse({
        "total_clicks": total,
        "today_clicks": today_clicks,
        "daily": {"labels": daily_labels, "counts": daily_counts},
        "forecast": {"labels": forecast_labels, "counts": preds},
        "devices": device_counts,
        "heatmap": {
            "weekday_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "block_labels": ["Night", "Morning", "Afternoon", "Evening"],
            "matrix": heat,
        },
        "meta": {
            "timezone": str(timezone.get_current_timezone()),
            "today": today.strftime("%Y-%m-%d"),
        }
    })
