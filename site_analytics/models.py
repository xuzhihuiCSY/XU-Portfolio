from django.db import models


class ClickEvent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=300, db_index=True, blank=True)
    referrer = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    device_type = models.CharField(
        max_length=20,
        choices=[("mobile", "Mobile"), ("computer", "Computer"), ("other", "Other")],
        db_index=True,
        default="other",
    )

    class Meta:
        indexes = [
            models.Index(fields=["created_at", "device_type"]),
            models.Index(fields=["created_at", "path"]),
        ]

    def __str__(self):
        return f"{self.created_at} {self.device_type} {self.path}"
