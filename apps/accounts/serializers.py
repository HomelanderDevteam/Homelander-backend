import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.phone import normalize_phone
from .models import KYCDocument, KYCSubmission, User


import os

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
    email = serializers.EmailField(max_length=255)
    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def validate_phone_number(self, value):
        if not value:
            return None

        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError(
                "An account with this phone number already exists."
            )

        return phone

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Passwords do not match."
            })

        candidate = User(
            first_name=attrs["first_name"],
            last_name=attrs["last_name"],
            email=attrs["email"],
            phone_number=attrs.get("phone_number"),
        )

        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "password": list(exc.messages)
            })

        return attrs



class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        help_text="Registered email address"
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        return value.strip().lower()



class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(
        write_only=True,
        trim_whitespace=True,
    )

    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    def validate_phone_number(self, value):
        if not value:
            return None

        try:
            return normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))





class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()



class ProfileUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        max_length=255,
        required=False,
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(
            email__iexact=value
        ).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

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

KYC_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
KYC_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
KYC_MAX_DOCUMENTS = 5


class KYCSubmitSerializer(serializers.Serializer):
    document_types = serializers.ListField(
        child=serializers.ChoiceField(choices=KYCDocument.DocumentType.choices),
        allow_empty=False, max_length=KYC_MAX_DOCUMENTS,
    )
    documents = serializers.ListField(
        child=serializers.FileField(), allow_empty=False, max_length=KYC_MAX_DOCUMENTS,
    )

    def validate_documents(self, files):
        for f in files:
            if os.path.splitext(f.name)[1].lower() not in KYC_ALLOWED_EXTENSIONS:
                raise serializers.ValidationError("Only JPG, PNG or PDF files are allowed.")
            if f.size > KYC_MAX_FILE_SIZE:
                raise serializers.ValidationError("Each file must be 5 MB or smaller.")
        return files

    def validate(self, attrs):
        if len(attrs["document_types"]) != len(attrs["documents"]):
            raise serializers.ValidationError(
                "Send one document type for each file, in the same order."
            )
        return attrs


class KYCSubmissionSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = ["id", "submission_reference", "status", "submitted_at",
                  "reviewed_at", "rejection_reason", "documents"]
        read_only_fields = fields

    def get_documents(self, obj):
        # No file links on purpose: KYC files are never exposed to the app.
        return [{"id": str(d.id), "document_type": d.document_type, "uploaded_at": d.uploaded_at}
                for d in obj.documents.all()]