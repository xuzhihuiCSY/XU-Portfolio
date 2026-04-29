from django.urls import path
from .views import ads_txt, app_ads_txt, home, privacy, robots_txt, sitemap_xml

urlpatterns = [
    path("", home, name="home"),
    path("contact/", home, name="contact"),
    path("privacy/", privacy, name="privacy"),
    path("ads.txt", ads_txt, name="ads_txt"),
    path("app-ads.txt", app_ads_txt, name="app_ads_txt"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
]
