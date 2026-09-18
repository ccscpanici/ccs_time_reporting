from django.contrib import admin

from absence.models import AbsenceArtifact, AbsenceRequest, AbsenceRequestDay, PTOAccount, PTOAccountChange, PTOImport, PTOImportRow


@admin.register(PTOAccount)
class PTOAccountAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "vacation_weeks_per_year",
        "vacation_accrual",
        "vacation_used_minutes",
        "calculated_vacation_balance",
        "sick_available",
        "sick_used_minutes",
        "balance_as_of",
        "updated_at",
    )
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")
    readonly_fields = ("updated_at",)

    @admin.display(description="Vacation Accrual")
    def vacation_accrual(self, obj):
        return obj.vacation_accrual_minutes

    @admin.display(description="Vacation Balance")
    def calculated_vacation_balance(self, obj):
        return obj.calculated_vacation_balance_minutes

    @admin.display(description="Sick Available")
    def sick_available(self, obj):
        return obj.sick_available_minutes


class PTOImportRowInline(admin.TabularInline):
    model = PTOImportRow
    extra = 0
    readonly_fields = (
        "row_number", "employee_name", "employee", "match_status", "match_message",
        "sick_available_minutes", "sick_used_minutes", "vacation_available_minutes", "vacation_used_minutes",
    )


@admin.register(PTOImport)
class PTOImportAdmin(admin.ModelAdmin):
    list_display = ("source_name", "report_date", "status", "uploaded_by", "uploaded_at", "applied_by", "applied_at")
    list_filter = ("status", "report_date")
    readonly_fields = ("uploaded_at", "applied_at")
    inlines = [PTOImportRowInline]


@admin.register(PTOAccountChange)
class PTOAccountChangeAdmin(admin.ModelAdmin):
    list_display = ("pto_account", "source", "changed_by", "changed_at", "new_vacation_balance_minutes", "new_sick_balance_minutes")
    list_filter = ("source", "changed_at")
    search_fields = ("pto_account__employee__username", "pto_account__employee__first_name", "pto_account__employee__last_name")
    readonly_fields = [field.name for field in PTOAccountChange._meta.fields]


class AbsenceRequestDayInline(admin.TabularInline):
    model = AbsenceRequestDay
    extra = 0


@admin.register(AbsenceRequest)
class AbsenceRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "absence_type", "start_date", "end_date", "status", "manager", "late_notice", "negative_balance_exception_required")
    list_filter = ("absence_type", "status", "late_notice", "negative_balance_exception_required")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name", "manager__first_name", "manager__last_name")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "finalized_at")
    inlines = [AbsenceRequestDayInline]


@admin.register(AbsenceArtifact)
class AbsenceArtifactAdmin(admin.ModelAdmin):
    list_display = ("filename", "request", "generated_by", "generated_at")
    search_fields = ("filename", "request__employee__first_name", "request__employee__last_name")
    readonly_fields = ("generated_at", "sha256")
