"""Read-only queries for the accounts app."""
from common.phone import normalize_phone

from .models import User


def get_user_by_identifier(identifier):
    """Find a user by phone number or email. Returns None if nothing matches."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    if "@" in identifier:
        return User.objects.filter(email=identifier.lower()).first()
    try:
        phone = normalize_phone(identifier)
    except ValueError:
        return None
    return User.objects.filter(phone_number=phone).first()
