from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from labor.views import (
    LABOR_CACHE_KEY,
    LABOR_CACHE_TTL,
    LABOR_STALE_KEY,
    LABOR_STALE_TTL,
    _build_labor_payload,
)


class Command(BaseCommand):
    help = "Preload labor/FRED data cache to reduce first-request failures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Return non-zero exit code if warm-up fails.",
        )

    def handle(self, *args, **options):
        try:
            payload = _build_labor_payload()
            cache.set(LABOR_CACHE_KEY, payload, LABOR_CACHE_TTL)
            cache.set(LABOR_STALE_KEY, payload, LABOR_STALE_TTL)
            self.stdout.write(self.style.SUCCESS("Labor cache warm-up complete."))
        except Exception as exc:
            msg = f"Labor cache warm-up failed: {exc}"
            if options["strict"]:
                raise CommandError(msg)
            self.stderr.write(self.style.WARNING(msg))
