import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import WaitlistEntry


def _safe(value):
    """Stops spreadsheet programs from running a cell that starts with = + - or @."""
    value = value or ""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "phone_number", "interested_as", "created_at")
    list_filter = ("interested_as", "created_at")
    search_fields = ("email", "full_name", "phone_number")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    actions = ["export_csv"]

    @admin.action(description="Export selected as CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="waitlist.csv"'
        writer = csv.writer(response)
        writer.writerow(["email", "full_name", "phone_number", "interested_as", "joined_at"])
        for e in queryset:
            writer.writerow([
                _safe(e.email), _safe(e.full_name), _safe(e.phone_number),
                e.interested_as, e.created_at.isoformat(),
            ])
        return response