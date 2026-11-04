from django.contrib.auth.base_user import BaseUserManager

from common.phone import normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, phone_number):
        try:
            phone_number = normalize_phone(phone_number)
        except ValueError:
            raise self.model.DoesNotExist
        return self.get(phone_number=phone_number)

    def _create_user(self, phone_number, password, **extra_fields):
        if not phone_number:
            raise ValueError("The phone number must be set.")
        phone_number = normalize_phone(phone_number)
        email = extra_fields.pop("email", None)
        email = email.strip().lower() if email else None
        user = self.model(phone_number=phone_number, email=email or None, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(phone_number, password, **extra_fields)
