"""Application support code for admin."""

from django.contrib import admin
from .models import EmployeeProfile, OfficeLocation, UserPreference, AccountNotificationRecipient


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    """Provide office location admin behavior for this module."""
    list_display = ("name", "address_1", "address_2", "city", "state", "postal_code", "active")
    list_filter = ("active", "state")
    search_fields = ("name", "address_1", "city", "postal_code")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    """Provide employee profile admin behavior for this module."""
    list_display = ("user", "employee_code", "department", "office_location", "supervisor", "city", "state")
    list_filter = ("office_location", "department", "state", "supervisor")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "supervisor__username",
        "supervisor__first_name",
        "supervisor__last_name",
        "employee_code",
        "department",
        "address_1",
        "city",
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Provide the formfield for foreignkey operation for this module."""
        if db_field.name == "supervisor":
            from django.contrib.auth.models import User
            kwargs["queryset"] = User.objects.filter(groups__name="ProjectManagers", is_active=True).distinct().order_by("last_name", "first_name", "username")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    """Provide user preference admin behavior for this module."""
    list_display = ("user", "color_scheme", "theme")
    list_filter = ("color_scheme", "theme")

@admin.register(AccountNotificationRecipient)
class AccountNotificationRecipientAdmin(admin.ModelAdmin):
    """Provide account notification recipient admin behavior for this module."""
    list_display = ("email", "name", "active")
    list_filter = ("active",)
    search_fields = ("email", "name")
    ordering = ("email",)
