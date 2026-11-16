import logging

from .models import WaitlistEntry

logger = logging.getLogger(__name__)


def join_waitlist(*, email, full_name="", phone_number="", interested_as=""):
    """Add someone to the waitlist. Joining twice is not an error. Returns True if new."""
    _, created = WaitlistEntry.objects.get_or_create(
        email=email,
        defaults={
            "full_name": full_name,
            "phone_number": phone_number,
            "interested_as": interested_as,
        },
    )
    if created:
        logger.info("Waitlist signup added")
    return created