import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, ALLOWED_HOSTS, SECRET_KEY, env_bool, env_list

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable is required in production.")

DEBUG = False

# Serve static files (admin CSS, API docs) from the app itself.
MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# Render (and similar hosts) tell us the public hostname through an environment variable.
render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_host:
    ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [render_host]
    CSRF_TRUSTED_ORIGINS = [f"https://{render_host}"]
CSRF_TRUSTED_ORIGINS = list(globals().get("CSRF_TRUSTED_ORIGINS", [])) + env_list("CSRF_TRUSTED_ORIGINS")

# Behind a proxy that terminates HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
