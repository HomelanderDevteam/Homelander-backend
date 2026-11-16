import uuid

from django.db import models
from django.utils import timezone


class WaitlistEntry(models.Model):
    class Interest(models.TextChoices):  # optional field, remove it if your team doesn't want it
        BUYER = "BUYER", "Buyer"
        OWNER = "OWNER", "Property owner"
        AGENT = "AGENT", "Agent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    interested_as = models.CharField(max_length=20, choices=Interest.choices, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "waitlist_entries"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email