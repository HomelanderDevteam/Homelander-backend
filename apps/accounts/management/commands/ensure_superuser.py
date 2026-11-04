"""Create the first admin from environment variables (handy on hosts with no shell access).

Needs: ADMIN_PHONE_NUMBER, ADMIN_PASSWORD (optional: ADMIN_FIRST_NAME, ADMIN_LAST_NAME, ADMIN_EMAIL).
Safe to run on every deploy: it does nothing if the user already exists.
"""
import os

from django.core.management.base import BaseCommand

from apps.accounts.selectors import get_user_by_identifier
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a superuser from ADMIN_* environment variables if it does not exist."

    def handle(self, *args, **options):
        phone = os.environ.get("ADMIN_PHONE_NUMBER")
        password = os.environ.get("ADMIN_PASSWORD")
        if not phone or not password:
            self.stdout.write("ADMIN_PHONE_NUMBER / ADMIN_PASSWORD not set; skipping.")
            return
        if get_user_by_identifier(phone):
            self.stdout.write("Admin user already exists; skipping.")
            return
        User.objects.create_superuser(
            phone_number=phone,
            password=password,
            first_name=os.environ.get("ADMIN_FIRST_NAME", "Admin"),
            last_name=os.environ.get("ADMIN_LAST_NAME", "User"),
            email=os.environ.get("ADMIN_EMAIL") or None,
        )
        self.stdout.write(self.style.SUCCESS("Admin user created."))
