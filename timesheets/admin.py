
from django.contrib import admin, messages
from django import forms
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from .models import ApprovalNotificationRecipient, Customer, EmailConfiguration, Expense, Job, MileageRate, PartEntry, TimeEntry, Timesheet, TimesheetImport, TimesheetReceipt, TimesheetSubmissionArtifact, TimesheetSubmissionRecipient, WorkCode
from .services.notifications import send_test_email


class EmailConfigurationAdminForm(forms.ModelForm):
    smtp_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Microsoft 365 SMTP password or app password for the SMTP username.",
    )

    class Meta:
        model = EmailConfiguration
        fields = "__all__"


@admin.register(EmailConfiguration)
class EmailConfigurationAdmin(admin.ModelAdmin):
    form = EmailConfigurationAdminForm
    list_display = (
        "name",
        "from_email",
        "reply_to_email",
        "smtp_host",
        "smtp_port",
        "active",
        "last_test_success",
        "last_test_sent_at",
    )
    list_filter = ("active", "use_tls", "use_ssl", "last_test_success")
    readonly_fields = ("last_test_sent_at", "last_test_success", "last_test_message", "updated_at")
    fieldsets = (
        ("Email Identity", {
            "fields": ("name", "from_email", "reply_to_email", "active")
        }),
        ("Microsoft 365 / SMTP Settings", {
            "fields": ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "use_tls", "use_ssl")
        }),
        ("Test Email", {
            "fields": ("test_recipient", "last_test_sent_at", "last_test_success", "last_test_message")
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:object_id>/send-test-email/",
                self.admin_site.admin_view(self.send_test_email_view),
                name="timesheets_emailconfiguration_send_test_email",
            ),
        ]
        return custom_urls + urls

    def send_test_email_view(self, request, object_id):
        config = self.get_object(request, object_id)
        if not config:
            self.message_user(request, "Email configuration not found.", level=messages.ERROR)
            return redirect("../")

        try:
            send_test_email(config)
        except Exception as exc:
            config.last_test_sent_at = timezone.now()
            config.last_test_success = False
            config.last_test_message = str(exc)
            config.save(update_fields=["last_test_sent_at", "last_test_success", "last_test_message", "updated_at"])
            self.message_user(request, f"Test email failed: {exc}", level=messages.ERROR)
        else:
            config.last_test_sent_at = timezone.now()
            config.last_test_success = True
            config.last_test_message = "Test email sent successfully."
            config.save(update_fields=["last_test_sent_at", "last_test_success", "last_test_message", "updated_at"])
            self.message_user(request, "Test email sent successfully.", level=messages.SUCCESS)

        return redirect(f"../../{object_id}/change/")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_send_test_email"] = True
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


@admin.register(ApprovalNotificationRecipient)
class ApprovalNotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "active")
    list_filter = ("active",)
    search_fields = ("email", "name")




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
    list_display = ("job_number", "year", "job_month", "description", "customer", "job_status", "invoice_status", "work_type", "lead_display", "available_for_time_entry", "last_imported_at")
    list_filter = ("year", "job_month", "active", "job_status", "invoice_status", "work_type", "customer")
    search_fields = (
        "job_number",
        "description",
        "customer__name",
        "customer_po",
        "quote_number",
        "location",
        "lead",
        "lead_user__username",
        "lead_user__first_name",
        "lead_user__last_name",
        "engineer_01",
        "engineer_01_user__username",
        "engineer_01_user__first_name",
        "engineer_01_user__last_name",
        "engineer_02",
        "engineer_02_user__username",
        "engineer_02_user__first_name",
        "engineer_02_user__last_name",
        "engineer_03",
        "engineer_03_user__username",
        "engineer_03_user__first_name",
        "engineer_03_user__last_name",
        "engineer_04",
        "engineer_04_user__username",
        "engineer_04_user__first_name",
        "engineer_04_user__last_name",
        "engineer_05",
        "engineer_05_user__username",
        "engineer_05_user__first_name",
        "engineer_05_user__last_name",
        "engineer_06",
        "engineer_06_user__username",
        "engineer_06_user__first_name",
        "engineer_06_user__last_name",
        "engineer_07",
        "engineer_07_user__username",
        "engineer_07_user__first_name",
        "engineer_07_user__last_name",
        "engineer_08",
        "engineer_08_user__username",
        "engineer_08_user__first_name",
        "engineer_08_user__last_name",
        "engineer_09",
        "engineer_09_user__username",
        "engineer_09_user__first_name",
        "engineer_09_user__last_name",
        "engineer_10",
        "engineer_10_user__username",
        "engineer_10_user__first_name",
        "engineer_10_user__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "last_imported_at")

    @admin.display(description="Lead")
    def lead_display(self, obj):
        if obj.lead_user:
            full_name = obj.lead_user.get_full_name()
            return full_name or obj.lead_user.username
        return obj.lead

    @admin.display(boolean=True, description="Available for Time Entry")
    def available_for_time_entry(self, obj):
        return obj.active

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


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
