"""Business actions for the accounts app (the 'service functions').

Views and serializers stay thin. Every rule lives here, so the API, the staff admin
and background jobs all follow the same rules.
"""
import logging

from django.contrib.auth.models import update_last_login
from django.db import IntegrityError, transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from .exceptions import AccountDisabled, DuplicateAccount, InvalidCredentials, KYCAlreadyActive
from .models import KYCDocument, KYCSubmission, User

from .exceptions import AccountDisabled, DuplicateAccount, InvalidCredentials
from .models import User
from .selectors import get_user_by_identifier

logger = logging.getLogger(__name__)


def issue_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def register_user(*, first_name, last_name, phone_number, password, email=None):
    """Create an account. Everyone starts as a normal user with no special role."""
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                phone_number=phone_number,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
    except IntegrityError:
        # Two people registering the same number at the same moment.
        raise DuplicateAccount()
    logger.info("User registered: %s", user.id)
    return user


def login_user(*, identifier, password):
    """Check credentials and return (user, tokens)."""
    user = get_user_by_identifier(identifier)
    if user is None:
        User().set_password(password)  # keep timing similar for unknown users
        logger.warning("Login failed: unknown identifier")
        raise InvalidCredentials()
    if not user.check_password(password):
        logger.warning("Login failed: wrong password for user %s", user.id)
        raise InvalidCredentials()
    if not user.is_active:
        logger.warning("Login blocked: inactive user %s", user.id)
        raise AccountDisabled()
    update_last_login(None, user)
    logger.info("User logged in: %s", user.id)
    return user, issue_tokens_for_user(user)


def logout_user(*, refresh_token):
    """Blacklist the refresh token. An invalid or expired token counts as already logged out."""
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError:
        pass


def revoke_all_tokens(user):
    """Log the user out of every device."""
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


def change_password(*, user, new_password):
    """Change the password, sign out all devices, return fresh tokens for this one.

    The serializer has already checked the old password and the new password's strength.
    """
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoke_all_tokens(user)
    logger.info("Password changed: %s", user.id)
    return issue_tokens_for_user(user)


def update_profile(*, user, **fields):
    for name, value in fields.items():
        setattr(user, name, value)
    user.save()
    return user

def submit_kyc(*, user, documents):
    """documents is a list of (document_type, file) pairs."""
    active = KYCSubmission.objects.filter(
        user=user, status__in=[KYCSubmission.Status.PENDING, KYCSubmission.Status.APPROVED]
    )
    if active.exists():
        raise KYCAlreadyActive()
    try:
        with transaction.atomic():
            submission = KYCSubmission.objects.create(user=user)
            for document_type, file in documents:
                KYCDocument.objects.create(
                    kyc_submission=submission, document_type=document_type, document=file
                )
    except IntegrityError:
        # Two requests at the same moment; the database rule caught it.
        raise KYCAlreadyActive()
    logger.info("KYC submitted: %s by user %s", submission.submission_reference, user.id)
    return submission