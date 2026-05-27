from django.contrib import admin
from .models import EmployeeProfile, OfficeLocation, UserPreference


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "address_1", "address_2", "city", "state", "postal_code", "active")
    list_filter = ("active", "state")
    search_fields = ("name", "address_1", "city", "postal_code")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "employee_code", "department", "office_location", "city", "state")
    list_filter = ("office_location", "department", "state")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "employee_code",
        "department",
        "address_1",
        "city",
    )


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "color_scheme", "theme")
    list_filter = ("color_scheme", "theme")
