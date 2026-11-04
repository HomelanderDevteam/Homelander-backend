from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = SECRET_KEY or "dev-only-insecure-key-change-me-0123456789abcdef"  # noqa: F405
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
