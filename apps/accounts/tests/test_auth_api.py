from django.contrib.auth import authenticate
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

PASSWORD = "Sup3r-Secret-Pass"


def make_user(phone="08012345678", email="ada@example.com", password=PASSWORD, **extra):
    return User.objects.create_user(phone, password, first_name="Ada", last_name="Obi", email=email, **extra)


class BaseAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the cache

    def auth(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


class RegisterTests(BaseAPITest):
    url = "/api/v1/auth/register/"
    payload = {
        "first_name": "Ada", "last_name": "Obi", "phone_number": "0801 234 5678",
        "email": "Ada@Example.com", "password": PASSWORD, "password_confirm": PASSWORD,
    }

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["user"]["phone_number"], "+2348012345678")
        self.assertEqual(response.data["user"]["email"], "ada@example.com")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn("password", response.data["user"])

    def test_new_token_works_on_protected_endpoint(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.auth(response.data["access"])
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["first_name"], "Ada")

    def test_email_is_optional(self):
        payload = {**self.payload}
        del payload["email"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["user"]["email"])

    def test_cannot_make_yourself_staff_or_admin(self):
        payload = {**self.payload, "is_staff": True, "is_superuser": True, "role": "admin", "is_active": False}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(phone_number="+2348012345678")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_duplicate_phone_in_any_format_is_rejected(self):
        make_user()
        response = self.client.post(self.url, {**self.payload, "phone_number": "+234 801 234 5678", "email": "x@y.com"},
                                    format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.data)

    def test_duplicate_email_is_rejected_regardless_of_case(self):
        make_user(phone="08099999999")
        response = self.client.post(self.url, {**self.payload, "email": "ADA@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(self.url, {**self.payload, "password_confirm": "different"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password_confirm", response.data)

    def test_weak_passwords_are_rejected(self):
        for weak in ["short1", "12345678", "password", "08012345678"]:
            response = self.client.post(self.url, {**self.payload, "password": weak, "password_confirm": weak},
                                        format="json")
            self.assertEqual(response.status_code, 400, weak)
            self.assertIn("password", response.data, weak)

    def test_invalid_phone_is_rejected(self):
        response = self.client.post(self.url, {**self.payload, "phone_number": "12345"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.data)

    def test_missing_fields_are_reported(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        for field in ["first_name", "last_name", "phone_number", "password", "password_confirm"]:
            self.assertIn(field, response.data)

    def test_expired_or_garbage_token_does_not_block_registration(self):
        self.auth("not-a-real-token")
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201)


class LoginTests(BaseAPITest):
    url = "/api/v1/auth/login/"

    def setUp(self):
        super().setUp()
        self.user = make_user()

    def test_login_with_phone_in_different_formats(self):
        for identifier in ["08012345678", "+2348012345678", "0801 234 5678"]:
            response = self.client.post(self.url, {"identifier": identifier, "password": PASSWORD}, format="json")
            self.assertEqual(response.status_code, 200, identifier)
            self.assertEqual(response.data["user"]["id"], str(self.user.id))

    def test_login_with_email_case_insensitive(self):
        response = self.client.post(self.url, {"identifier": "ADA@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_sets_last_login(self):
        self.assertIsNone(User.objects.get(pk=self.user.pk).last_login)
        self.client.post(self.url, {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.assertIsNotNone(User.objects.get(pk=self.user.pk).last_login)

    def test_wrong_password_and_unknown_user_give_the_same_error(self):
        wrong = self.client.post(self.url, {"identifier": "08012345678", "password": "nope"}, format="json")
        unknown = self.client.post(self.url, {"identifier": "08000000000", "password": "nope"}, format="json")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.data["detail"], unknown.data["detail"])

    def test_inactive_user_is_blocked_with_clear_message(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"].code, "account_disabled")

    def test_inactive_user_with_wrong_password_is_not_told_the_account_is_disabled(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {"identifier": "08012345678", "password": "nope"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_missing_fields(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_stale_token_in_header_does_not_block_login(self):
        self.auth("stale.token.value")
        response = self.client.post(self.url, {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_login_is_rate_limited(self):
        statuses = [self.client.post(self.url, {"identifier": "08012345678", "password": "bad"}, format="json").status_code
                    for _ in range(25)]
        self.assertIn(429, statuses)
        self.assertEqual(statuses[0], 401)

    def test_django_authenticate_backend_works_for_the_admin_login(self):
        self.assertEqual(authenticate(username="08012345678", password=PASSWORD), self.user)
        self.assertEqual(authenticate(username="ada@example.com", password=PASSWORD), self.user)
        self.assertIsNone(authenticate(username="08012345678", password="wrong"))


class TokenTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        login = self.client.post("/api/v1/auth/login/", {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.access, self.refresh = login.data["access"], login.data["refresh"]

    def test_protected_endpoint_requires_a_token(self):
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_refresh_returns_new_tokens_and_old_refresh_stops_working(self):
        first = self.client.post("/api/v1/auth/token/refresh/", {"refresh": self.refresh}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertIn("access", first.data)
        self.assertIn("refresh", first.data)
        self.assertNotEqual(first.data["refresh"], self.refresh)
        reuse = self.client.post("/api/v1/auth/token/refresh/", {"refresh": self.refresh}, format="json")
        self.assertEqual(reuse.status_code, 401)

    def test_refresh_refused_for_deactivated_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_refresh_with_garbage_token(self):
        response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": "garbage"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_logout_blacklists_refresh_token(self):
        response = self.client.post("/api/v1/auth/logout/", {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, 200)
        after = self.client.post("/api/v1/auth/token/refresh/", {"refresh": self.refresh}, format="json")
        self.assertEqual(after.status_code, 401)

    def test_logout_works_without_an_access_token_and_is_repeatable(self):
        self.client.credentials()  # no Authorization header
        self.assertEqual(self.client.post("/api/v1/auth/logout/", {"refresh": self.refresh}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout/", {"refresh": self.refresh}, format="json").status_code, 200)

    def test_logout_with_invalid_token_is_harmless_and_missing_token_is_a_400(self):
        self.assertEqual(self.client.post("/api/v1/auth/logout/", {"refresh": "junk"}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout/", {}, format="json").status_code, 400)


class ProfileTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        login = self.client.post("/api/v1/auth/login/", {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.auth(login.data["access"])

    def test_get_me(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phone_number"], "+2348012345678")
        self.assertEqual(response.data["full_name"], "Ada Obi")
        self.assertFalse(response.data["is_staff"])

    def test_patch_updates_name_and_email(self):
        response = self.client.patch("/api/v1/auth/me/", {"first_name": "Adaeze", "email": "NEW@Example.com"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Adaeze")
        self.assertEqual(self.user.email, "new@example.com")

    def test_patch_cannot_change_phone_or_privileges(self):
        self.client.patch("/api/v1/auth/me/", {"phone_number": "08000000001", "is_staff": True, "is_superuser": True},
                          format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "+2348012345678")
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_patch_rejects_an_email_used_by_someone_else(self):
        make_user(phone="08055555555", email="taken@example.com")
        response = self.client.patch("/api/v1/auth/me/", {"email": "taken@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_patch_can_remove_email(self):
        response = self.client.patch("/api/v1/auth/me/", {"email": ""}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.email)

    def test_keeping_your_own_email_is_fine(self):
        response = self.client.patch("/api/v1/auth/me/", {"email": "ada@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)


class ChangePasswordTests(BaseAPITest):
    url = "/api/v1/auth/password/change/"
    NEW = "An0ther-Strong-Pass"

    def setUp(self):
        super().setUp()
        self.user = make_user()
        login = self.client.post("/api/v1/auth/login/", {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.access, self.refresh = login.data["access"], login.data["refresh"]
        self.auth(self.access)

    def body(self, **over):
        return {"old_password": PASSWORD, "new_password": self.NEW, "new_password_confirm": self.NEW, **over}

    def test_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.client.post(self.url, self.body(), format="json").status_code, 401)

    def test_wrong_old_password_is_a_400_not_a_401(self):
        response = self.client.post(self.url, self.body(old_password="wrong"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.data)

    def test_mismatch_and_weak_passwords_are_rejected(self):
        self.assertEqual(self.client.post(self.url, self.body(new_password_confirm="x"), format="json").status_code, 400)
        weak = self.client.post(self.url, self.body(new_password="12345678", new_password_confirm="12345678"), format="json")
        self.assertEqual(weak.status_code, 400)

    def test_success_changes_password_revokes_old_sessions_and_returns_new_tokens(self):
        response = self.client.post(self.url, self.body(), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        self.client.credentials()
        old_login = self.client.post("/api/v1/auth/login/", {"identifier": "08012345678", "password": PASSWORD}, format="json")
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post("/api/v1/auth/login/", {"identifier": "08012345678", "password": self.NEW}, format="json")
        self.assertEqual(new_login.status_code, 200)

        old_refresh = self.client.post("/api/v1/auth/token/refresh/", {"refresh": self.refresh}, format="json")
        self.assertEqual(old_refresh.status_code, 401)
        new_refresh = self.client.post("/api/v1/auth/token/refresh/", {"refresh": response.data["refresh"]}, format="json")
        self.assertEqual(new_refresh.status_code, 200)
