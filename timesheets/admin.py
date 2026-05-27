
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from .models import Customer, Expense, Job, MileageRate, PartEntry, TimeEntry, Timesheet, TimesheetImport, TimesheetReceipt, TimesheetSubmissionArtifact, TimesheetSubmissionRecipient, WorkCode


class TimeEntryInline(admin.TabularInline):
    model = TimeEntry
    extra = 0


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ("employee", "week_start", "mileage_rate", "status", "submitted_at", "reopened_at", "approved_at", "invoiced_at", "deleted_at")
    list_filter = ("status", "week_start", "submitted_at", "approved_at", "invoiced_at", "deleted_at")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")
    inlines = [TimeEntryInline]
    change_list_template = "admin/timesheets/timesheet/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "clear-all/",
                self.admin_site.admin_view(self.clear_all_timesheets),
                name="timesheets_timesheet_clear_all",
            ),
        ]
        return custom_urls + urls

    def clear_all_timesheets(self, request):
        if request.method == "POST":
            count = Timesheet.objects.count()
            Timesheet.objects.all().delete()
            self.message_user(
                request,
                f"Cleared {count} timesheet(s). Related time entries, expenses, parts, receipts, and artifacts were deleted by cascade.",
                level=messages.WARNING,
            )
            return redirect("../")

        context = {
            **self.admin_site.each_context(request),
            "title": "Clear ALL Timesheets",
            "timesheet_count": Timesheet.objects.count(),
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/timesheets/timesheet/clear_all_confirmation.html",
            context,
        )


@admin.register(WorkCode)
class WorkCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "active", "allows_overtime", "display_order")
    list_filter = ("active", "allows_overtime")
    search_fields = ("code", "description")
    ordering = ("display_order", "code")


@admin.register(MileageRate)
class MileageRateAdmin(admin.ModelAdmin):
    list_display = ("year", "rate")
    search_fields = ("year",)
    ordering = ("-year",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("job_number", "description", "customer", "active")
    list_filter = ("active", "customer")
    search_fields = ("job_number", "description", "customer__name")


admin.site.register(Customer)
admin.site.register(Expense)

@admin.register(PartEntry)
class PartEntryAdmin(admin.ModelAdmin):
    list_display = ("time_entry", "ee_stock_job_number", "quantity", "part_description_part_number", "reorder_part")
    list_filter = ("reorder_part",)
    search_fields = (
        "ee_stock_job_number",
        "part_description_part_number",
        "additional_notes_for_customer",
        "time_entry__job_number",
    )

admin.site.register(TimesheetImport)


@admin.register(TimesheetSubmissionArtifact)
class TimesheetSubmissionArtifactAdmin(admin.ModelAdmin):
    list_display = ("timesheet", "file_type", "export_format", "created_at", "created_by")
    list_filter = ("file_type", "export_format", "created_at")
    search_fields = ("timesheet__employee__username", "timesheet__employee__first_name", "timesheet__employee__last_name", "file")
    readonly_fields = ("created_at",)

admin.site.register(TimesheetSubmissionRecipient)


@admin.register(TimesheetReceipt)
class TimesheetReceiptAdmin(admin.ModelAdmin):
    list_display = ("timesheet", "original_filename", "description", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = (
        "original_filename",
        "description",
        "timesheet__employee__username",
        "timesheet__employee__first_name",
        "timesheet__employee__last_name",
    )
    readonly_fields = ("uploaded_at",)
