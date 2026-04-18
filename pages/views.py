from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages

def _home_context():
    return {
        "site_name": "XU-Portfolio",
        "headline": "Hi, I'm Zhihui (Xu).",
        "tagline": "I build software, AI tools, and practical projects.",
    }

def home(request):
    # homepage render
    return render(request, "pages/home.html", _home_context())


def privacy(request):
    return render(request, "pages/privacy.html", {
        "site_name": "XU-Portfolio",
        "app_name": "SnakeGame",
        "contact_email": "xuzhihuieateat@gmail.com",
        "last_updated": "2026-04-15",
    })


def ads_txt(request):
    content = "google.com, pub-4558912554658127, DIRECT, f08c47fec0942fa0\n"
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    content = f"""User-agent: *
Allow: /

Sitemap: {sitemap_url}
"""
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    urls = [
        request.build_absolute_uri("/"),
        request.build_absolute_uri("/privacy/"),
        request.build_absolute_uri("/stocks/"),
    ]
    xml = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *[f"  <url><loc>{url}</loc></url>" for url in urls],
            "</urlset>",
        ]
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")

def contact(request):
    """
    Handles the Contact Me form submission.
    POST -> validate -> flash message -> redirect back to #contact on homepage
    GET  -> just redirect to homepage contact section
    """
    if request.method == "GET":
        return redirect("/#contact")

    # POST
    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    subject = (request.POST.get("subject") or "").strip()
    message = (request.POST.get("message") or "").strip()

    # simple validation
    if not (name and email and subject and message):
        messages.error(request, "Please fill out all fields.")
        return redirect("/#contact")

    # TODO later:
    # - send email to yourself
    # - save to DB
    # - add anti-spam / rate limit
    messages.success(request, "Thanks! Your message was received — I’ll get back to you soon.")
    return redirect("/#contact")
