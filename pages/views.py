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
