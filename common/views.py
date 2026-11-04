from django.db import connection
from django.http import JsonResponse


def health(request):
    """Used by the hosting platform (and you) to check the service is alive."""
    try:
        connection.ensure_connection()
        database = "ok"
    except Exception:
        database = "unavailable"
    status = 200 if database == "ok" else 503
    return JsonResponse({"status": "ok" if status == 200 else "degraded", "database": database}, status=status)
