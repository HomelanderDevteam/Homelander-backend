from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_normalises_phone_and_email(self):
        user = User.objects.create_user("0801 234 5678", "pass12345!", first_name="Ada", last_name="Obi",
                                        email="  ADA@Example.COM ")
        self.assertEqual(user.phone_number, "+2348012345678")
        self.assertEqual(user.email, "ada@example.com")
        self.assertTrue(user.check_password("pass12345!"))
        self.assertNotEqual(user.password, "pass12345!")  # stored scrambled

    def test_user_has_uuid_id_and_no_special_flags(self):
        user = User.objects.create_user("08012345678", "pass12345!", first_name="A", last_name="B")
        self.assertEqual(len(str(user.id)), 36)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_blank_email_is_stored_as_null_so_many_users_can_skip_email(self):
        User.objects.create_user("08012345678", "pass12345!", first_name="A", last_name="B", email="")
        second = User.objects.create_user("08087654321", "pass12345!", first_name="C", last_name="D", email="")
        self.assertIsNone(second.email)

    def test_phone_number_must_be_unique(self):
        User.objects.create_user("08012345678", "pass12345!", first_name="A", last_name="B")
        with self.assertRaises(IntegrityError):
            User.objects.create_user("+2348012345678", "pass12345!", first_name="C", last_name="D")

    def test_phone_is_required_and_must_be_valid(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", "pass12345!", first_name="A", last_name="B")
        with self.assertRaises(ValueError):
            User.objects.create_user("12", "pass12345!", first_name="A", last_name="B")

    def test_create_superuser(self):
        admin = User.objects.create_superuser("08012345678", "pass12345!", first_name="A", last_name="B")
        self.assertTrue(admin.is_staff and admin.is_superuser)

    def test_get_by_natural_key_accepts_any_phone_format(self):
        user = User.objects.create_user("08012345678", "pass12345!", first_name="A", last_name="B")
        self.assertEqual(User.objects.get_by_natural_key("0801 234 5678"), user)
