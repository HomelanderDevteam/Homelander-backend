from django.contrib.auth.backends import ModelBackend

from .models import User


class IdentifierBackend(ModelBackend):
    """Authenticate users using email and password."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get("email")

        if not email or password is None:
            return None

        email = email.strip().lower()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None