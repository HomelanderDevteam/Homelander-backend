from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User


class HealthAndDocsTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_swagger_docs_and_schema_load(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        schema = self.client.get("/api/schema/?format=json")
        self.assertEqual(schema.status_code, 200)
        paths = schema.json()["paths"]
        for path in ["/api/v1/auth/register/", "/api/v1/auth/login/", "/api/v1/auth/logout/",
                     "/api/v1/auth/token/refresh/", "/api/v1/auth/me/", "/api/v1/auth/password/change/"]:
            self.assertIn(path, paths)


class AdminTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser("08011111111", "Adm1n-Secret-Pass", first_name="Root", last_name="Admin")
        self.client.force_login(self.admin)

    def test_admin_pages_load_for_the_custom_user_model(self):
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/accounts/user/{self.admin.pk}/change/").status_code, 200)

    def test_admin_can_create_a_user_with_a_local_format_phone(self):
        response = self.client.post("/admin/accounts/user/add/", {
            "phone_number": "0802 222 3333", "first_name": "New", "last_name": "Staff", "email": "",
            "password1": "Str0ng-Admin-Made-Pass", "password2": "Str0ng-Admin-Made-Pass",
        })
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        self.assertTrue(User.objects.filter(phone_number="+2348022223333").exists())

    def test_admin_login_with_phone_or_email_style_identifier(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="0801 111 1111", password="Adm1n-Secret-Pass"))


class EnsureSuperuserCommandTests(TestCase):
    @override_settings()
    def test_creates_admin_from_environment_once(self):
        import os
        os.environ["ADMIN_PHONE_NUMBER"] = "08033334444"
        os.environ["ADMIN_PASSWORD"] = "Env-Admin-Pass-123"
        try:
            call_command("ensure_superuser")
            call_command("ensure_superuser")  # second run must not fail or duplicate
        finally:
            del os.environ["ADMIN_PHONE_NUMBER"], os.environ["ADMIN_PASSWORD"]
        users = User.objects.filter(phone_number="+2348033334444")
        self.assertEqual(users.count(), 1)
        self.assertTrue(users.first().is_superuser)
