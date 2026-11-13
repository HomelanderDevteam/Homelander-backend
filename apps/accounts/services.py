"""Business actions for the accounts app (the 'service functions').

Views and serializers stay thin. Every rule lives here, so the API, the staff admin
and background jobs all follow the same rules.
"""



import logging

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from rest_framework.exceptions import (
    AuthenticationFailed,
    PermissionDenied,
    ValidationError,
)

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from .exceptions import (
    AccountDisabled,
    DuplicateAccount,
    InvalidCredentials,
    KYCAlreadyActive,
)
from .models import KYCDocument, KYCSubmission, User

logger = logging.getLogger(__name__)





def issue_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}



def register_user(*, first_name, last_name, email, password, phone_number=None):
    """Create an account. Email is required; phone number is optional."""

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
            )

    except IntegrityError:
        raise DuplicateAccount()

    logger.info("User registered: %s", user.id)
    return user

def login_user(*, email, password):
    """Authenticate a user using email and password."""

    email = email.strip().lower()

    user = User.objects.filter(email=email).first()

    if user is None:
        User().set_password(password)
        logger.warning("Login failed: unknown email")
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


def verify_google_id_token(token):
    """
    Verify the Google ID token and return its claims.
    Google checks the signature, expiry, issuer and audience.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise ImproperlyConfigured(
            "GOOGLE_CLIENT_ID has not been configured."
        )

    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except (ValueError, GoogleAuthError):
        raise AuthenticationFailed("Invalid or expired Google ID token.")

    if not claims.get("sub"):
        raise AuthenticationFailed("Google account ID is missing.")

    if not claims.get("email") or claims.get("email_verified") is not True:
        raise AuthenticationFailed(
            "A verified Google email address is required."
        )

    return claims



def google_authenticate(*, token, phone_number=None):
    """
    Authenticate an existing Google user or register a new one.

    Email is obtained from Google's verified profile.
    Phone number is optional.

    Returns:
        (user, tokens)
    """

    claims = verify_google_id_token(token)

    google_sub = claims["sub"]
    email = claims["email"].strip().lower()

    # Check whether this Google account has already been registered.
    user = User.objects.filter(google_sub=google_sub).first()

    if user:
        if not user.is_active:
            raise PermissionDenied("This account has been disabled.")

        update_last_login(None, user)
        logger.info("User logged in with Google: %s", user.id)

        return user, issue_tokens_for_user(user)

    # Never automatically link a different account just because
    # it has the same email address.
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({
            "email": (
                "An account with this email already exists. "
                "Please log in using your existing method first."
            )
        })

    # Check phone uniqueness only when a phone number is supplied.
    if phone_number and User.objects.filter(
        phone_number=phone_number
    ).exists():
        raise ValidationError({
            "phone_number": "This phone number is already registered."
        })

    # Obtain names from Google's verified profile.
    first_name = claims.get("given_name", "").strip()
    last_name = claims.get("family_name", "").strip()

    if not first_name:
        full_name = claims.get("name", "").strip()
        name_parts = full_name.split(maxsplit=1)

        first_name = name_parts[0] if name_parts else email.split("@")[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=None,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                google_sub=google_sub,
            )

    except IntegrityError:
        # Handle simultaneous registration attempts safely.
        user = User.objects.filter(google_sub=google_sub).first()

        if user is None:
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError({
                    "email": "An account with this email already exists."
                })

            if phone_number and User.objects.filter(
                phone_number=phone_number
            ).exists():
                raise ValidationError({
                    "phone_number": "This phone number is already registered."
                })

            raise ValidationError(
                "Unable to create your account. Please try again."
            )

    if not user.is_active:
        raise PermissionDenied("This account has been disabled.")

    update_last_login(None, user)
    logger.info("New user registered with Google: %s", user.id)

    return user, issue_tokens_for_user(user)

