
"""Create the first admin from environment variables.

Required: ADMIN_EMAIL, ADMIN_PASSWORD
Optional: ADMIN_FIRST_NAME, ADMIN_LAST_NAME

Safe to run on every deploy: it does nothing if the email already exists.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a superuser from ADMIN_* environment variables if it does not exist."

    def handle(self, *args, **options):
        email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD")

        if not email or not password:
            self.stdout.write(
                "ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping."
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write("Admin user already exists; skipping.")
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name=os.environ.get("ADMIN_FIRST_NAME", "Admin"),
            last_name=os.environ.get("ADMIN_LAST_NAME", "User"),
        )

        self.stdout.write(self.style.SUCCESS("Admin user created."))
