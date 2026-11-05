import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import os

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

def kyc_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"kyc/{instance.kyc_submission.user_id}/{uuid.uuid4().hex}{ext}"


class KYCSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="kyc_submissions")
    submission_reference = models.CharField(max_length=100, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="kyc_reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        db_table = "kyc_submissions"
        ordering = ["-submitted_at"]
        constraints = [
            # One PENDING or APPROVED submission per user at a time.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status__in=["PENDING", "APPROVED"]),
                name="one_active_kyc_per_user",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "APPROVED", "REJECTED"]),
                name="kyc_status_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.status == self.Status.REJECTED and not (self.rejection_reason or "").strip():
            raise ValidationError({"rejection_reason": "Give a reason when rejecting."})
        if self.pk:
            previous = (
                KYCSubmission.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous and previous != self.status and previous != self.Status.PENDING:
                raise ValidationError(
                    {"status": "A reviewed submission can't be changed. The user must submit again."}
                )

    def save(self, *args, **kwargs):
        if not self.submission_reference:
            self.submission_reference = f"KYC-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.submission_reference} ({self.status})"


class KYCDocument(models.Model):
    class DocumentType(models.TextChoices):  # confirm this list with your teammate
        NATIONAL_ID = "NATIONAL_ID", "National ID"
        PASSPORT = "PASSPORT", "International passport"
        DRIVERS_LICENSE = "DRIVERS_LICENSE", "Driver's licence"
        VOTERS_CARD = "VOTERS_CARD", "Voter's card"
        SELFIE = "SELFIE", "Selfie"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kyc_submission = models.ForeignKey(KYCSubmission, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    document = models.FileField(upload_to=kyc_upload_path)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "kyc_documents"


