from django.utils import timezone
from .models import ClickEvent


BOT_HINTS = ("bot", "spider", "crawl", "slurp", "crawler", "facebookexternalhit")
STATIC_PREFIXES = ("/static/", "/media/", "/favicon.ico")


def guess_device_type(ua: str) -> str:
    ua_l = (ua or "").lower()
    if any(k in ua_l for k in ("iphone", "android", "ipad", "mobile")):
        return "mobile"
    if any(k in ua_l for k in ("windows", "macintosh", "linux", "x11")):
        return "computer"
    return "other"


class ClickLoggingMiddleware:
    """
    Logs GET page views as "clicks".
    - Skips admin, static/media, monitor endpoints
    - Skips common bots
    - Respects Do Not Track (DNT: 1)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if request.method != "GET":
                return response

            path = request.path or ""
            if path.startswith("/admin/") or path.startswith("/monitor/") or path.startswith("/analytics/"):
                return response
            if any(path.startswith(p) for p in STATIC_PREFIXES):
                return response

            # Only log “page” responses
            if response.status_code != 200:
                return response
            ctype = (response.get("Content-Type") or "")
            if "text/html" not in ctype:
                return response

            # Respect DNT
            if request.headers.get("DNT") == "1":
                return response

            ua = request.headers.get("User-Agent", "")
            ua_l = ua.lower()
            if any(k in ua_l for k in BOT_HINTS):
                return response

            ClickEvent.objects.create(
                created_at=timezone.now(),
                path=path[:300],
                referrer=(request.headers.get("Referer", "") or "")[:500],
                user_agent=ua[:500],
                device_type=guess_device_type(ua),
            )
        except Exception:
            # Don't break the site if logging fails
            pass

        return response
