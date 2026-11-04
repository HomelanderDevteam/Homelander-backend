"""Phone number normalisation.

Every phone number is stored in one format (E.164, for example +2348012345678) so
the same person can type "0801 234 5678" or "+234 801 234 5678" and still match.
"""
import re

from django.conf import settings

_SEPARATORS = re.compile(r"[\s\-().]")


def normalize_phone(raw, default_country_code=None):
    """Return the number as +<country code><number>, or raise ValueError."""
    code = default_country_code or getattr(settings, "DEFAULT_PHONE_COUNTRY_CODE", "234")
    value = _SEPARATORS.sub("", str(raw or ""))
    if value.startswith("00"):
        value = "+" + value[2:]

    if value.startswith("+"):
        digits = value[1:]
    elif value.startswith("0"):
        digits = code + value[1:]  # local format, e.g. 08012345678
    elif code == "234" and len(value) == 10 and value[0] in "789":
        digits = code + value  # Nigerian number typed without the leading 0
    elif value.startswith(code):
        digits = value
    else:
        raise ValueError("Enter a valid phone number, for example 08012345678 or +2348012345678.")

    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number, for example 08012345678 or +2348012345678.")
    if digits.startswith("234") and len(digits) != 13:
        raise ValueError("Nigerian phone numbers must have 11 digits (for example 08012345678).")
    return "+" + digits
