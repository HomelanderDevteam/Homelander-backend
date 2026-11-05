import os

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import KYCDocument, KYCSubmission, User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("phone_number", "first_name", "last_name", "email")


class UserChangeForm(DjangoUserChangeForm):
    class Meta(DjangoUserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ("-date_joined",)
    list_display = ("phone_number", "full_name", "email", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("phone_number", "email", "first_name", "last_name")
    readonly_fields = ("last_login", "date_joined", "updated_at")
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone_number", "first_name", "last_name", "email", "password1", "password2"),
        }),
    )
    actions = ["activate_users", "deactivate_users"]

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) activated.")

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{updated} user(s) deactivated.")

class KYCDocumentInline(admin.TabularInline):
    model = KYCDocument
    extra = 0
    can_delete = False
    fields = ("document_type", "uploaded_at", "view_file")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="File")
    def view_file(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:accounts_kycdocument_file", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Open file</a>', url)


@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ("submission_reference", "user", "status", "submitted_at", "reviewed_by")
    list_filter = ("status", "submitted_at")
    search_fields = ("submission_reference", "user__phone_number", "user__email",
                     "user__first_name", "user__last_name")
    ordering = ("-submitted_at",)
    fields = ("submission_reference", "user", "submitted_at", "status",
              "rejection_reason", "reviewed_by", "reviewed_at")
    readonly_fields = ("submission_reference", "user", "submitted_at", "reviewed_by", "reviewed_at")
    inlines = [KYCDocumentInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

    def get_urls(self):
        custom = [
            path("document/<uuid:doc_id>/",
                 self.admin_site.admin_view(self.download_document),
                 name="accounts_kycdocument_file"),
        ]
        return custom + super().get_urls()

    def download_document(self, request, doc_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        doc = get_object_or_404(KYCDocument, pk=doc_id)
        return FileResponse(doc.document.open("rb"), filename=os.path.basename(doc.document.name))
