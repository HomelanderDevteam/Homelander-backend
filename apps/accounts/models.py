import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from common.phone import normalize_phone

from .managers import UserManager


def _clean_email(value):
    return (value or "").strip().lower() or None


class User(AbstractBaseUser, PermissionsMixin):
    """The `users` table from the ERD.

    There is deliberately NO role field. Whether someone is an approved owner or agent
    comes from their approved applications (added with the KYC feature), not from a label.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    # password, last_login, is_superuser, groups, user_permissions come from the Django base classes

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        super().clean()
        self.email = _clean_email(self.email)
        try:
            self.phone_number = normalize_phone(self.phone_number)
        except ValueError as exc:
            raise ValidationError({"phone_number": str(exc)})

    def save(self, *args, **kwargs):
        self.email = _clean_email(self.email)  # blank email must be NULL so it stays unique
        super().save(*args, **kwargs)
