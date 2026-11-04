from django.contrib.auth.backends import ModelBackend

from .models import User
from .selectors import get_user_by_identifier


class IdentifierBackend(ModelBackend):
    """Lets Django (and the staff admin) log in with a phone number OR an email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("identifier")
        if not identifier or password is None:
            return None
        user = get_user_by_identifier(identifier)
        if user is None:
            User().set_password(password)  # same hashing cost whether or not the user exists
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
