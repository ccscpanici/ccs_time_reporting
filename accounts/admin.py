"""Application support code for admin."""

from django.contrib import admin
from .models import EmployeeProfile, OfficeLocation, UserPreference, AccountNotificationRecipient, CompanyOverhead


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    """Provide office location admin behavior for this module."""
    list_display = ("name", "address_1", "address_2", "city", "state", "postal_code", "active")
    list_filter = ("active", "state")
    search_fields = ("name", "address_1", "city", "postal_code")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    """Provide employee profile admin behavior for this module."""
    list_display = ("employee_name", "user", "employee_code", "title", "department", "office_location", "supervisor_name", "birthday", "employee_active")
    list_select_related = ("user", "supervisor", "office_location")
    ordering = ("user__last_name", "user__first_name", "user__username")
    list_filter = ("user__is_active", "office_location", "department", "supervisor")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "supervisor__username",
        "supervisor__first_name",
        "supervisor__last_name",
        "employee_code",
        "department",
        "title",
        "address_1",
        "city",
    )

    @admin.display(description="Employee", ordering="user__last_name")
    def employee_name(self, obj):
        return obj.user.get_full_name() or obj.user.get_username()

    @admin.display(description="Supervisor", ordering="supervisor__last_name")
    def supervisor_name(self, obj):
        if obj.supervisor_id is None:
            return "Not assigned"
        return obj.supervisor.get_full_name() or obj.supervisor.get_username()

    @admin.display(boolean=True, description="Active", ordering="user__is_active")
    def employee_active(self, obj):
        return obj.user.is_active

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

@admin.register(CompanyOverhead)
class CompanyOverheadAdmin(admin.ModelAdmin):
    """Financial overhead is visible and editable only to superusers."""

    list_display = ("name", "amount", "frequency", "annualized_amount", "effective_start", "effective_end", "active")
    list_filter = ("active", "frequency")
    search_fields = ("name",)
    ordering = ("name", "-effective_start")

    @admin.display(description="Annualized amount")
    def annualized_amount(self, obj):
        return obj.annual_amount

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_superuser)
