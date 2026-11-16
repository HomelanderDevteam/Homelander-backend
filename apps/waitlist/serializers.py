from rest_framework import serializers

from common.phone import normalize_phone

from .models import WaitlistEntry


class WaitlistJoinSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    interested_as = serializers.ChoiceField(
        choices=WaitlistEntry.Interest.choices, required=False, allow_blank=True
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_full_name(self, value):
        return value.strip()

    def validate_phone_number(self, value):
        value = value.strip()
        if not value:
            return ""
        try:
            return normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))