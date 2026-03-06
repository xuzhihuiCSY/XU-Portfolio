import os
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET


@require_GET
def ping(request):
    return JsonResponse({"ok": True})


@require_GET
def download_blob(request):
    """
    Serve N MB of data for download speed test.
    Example: /monitor/download?mb=5
    """
    try:
        mb = int(request.GET.get("mb", "5"))
        mb = max(1, min(mb, 20))  # clamp 1..20 MB
    except ValueError:
        return HttpResponseBadRequest("Invalid mb")

    size = mb * 1024 * 1024
    data = os.urandom(size)

    resp = HttpResponse(data, content_type="application/octet-stream")
    resp["Cache-Control"] = "no-store"
    return resp
