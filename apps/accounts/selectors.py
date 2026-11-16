"""Read-only queries for the accounts app."""

from .models import User


def get_user_by_email(email):
    """Find a user by email. Returns None if nothing matches."""
    if not email:
        return None

    email = email.strip().lower()
    return User.objects.filter(email=email).first()


def get_latest_kyc(user):
    return user.kyc_submissions.prefetch_related("documents").first()


def has_approved_kyc(user):
    """Used later by the properties app: no approved KYC means no listing."""
    return user.kyc_submissions.filter(status="APPROVED").exists()