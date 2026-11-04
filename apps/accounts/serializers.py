from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.phone import normalize_phone

from .models import User


def _validate_new_password(password, user):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))


# ---------------------------------------------------------------------------
# What the API returns
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "full_name", "phone_number", "email", "is_staff", "date_joined"]
        read_only_fields = fields


class AuthResponseSerializer(serializers.Serializer):
    """Documentation only: the shape returned by register and login."""

    user = UserSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    """Documentation only."""

    access = serializers.CharField()
    refresh = serializers.CharField()


# ---------------------------------------------------------------------------
# What the API accepts. Only the fields listed here can ever be set by the app.
# ---------------------------------------------------------------------------
class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=20)
    email = serializers.EmailField(max_length=255, required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_phone_number(self, value):
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return phone

    def validate_email(self, value):
        value = (value or "").strip().lower()
        if not value:
            return None
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        candidate = User(
            first_name=attrs["first_name"], last_name=attrs["last_name"],
            email=attrs.get("email"), phone_number=attrs["phone_number"],
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Phone number or email address")
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Fields a user may change about themselves. Phone number is not here on purpose:
    changing it must be verified first (added with phone verification)."""

    email = serializers.EmailField(max_length=255, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def validate_email(self, value):
        value = (value or "").strip().lower()
        if not value:
            return None
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        try:
            validate_password(attrs["new_password"], user=self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs
