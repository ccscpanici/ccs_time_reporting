from datetime import date, timedelta
from django import forms
from .models import Timesheet, TimesheetImport


class TimesheetCreateForm(forms.ModelForm):
    def clean_week_start(self):
        selected = self.cleaned_data["week_start"]
        # Timesheets are company work weeks starting on Sunday.
        # Python weekday(): Monday=0 ... Sunday=6.
        if selected.weekday() != 6:
            raise forms.ValidationError("Please choose a Sunday for the timesheet week start.")
        return selected

    def clean_entries_per_day(self):
        value = self.cleaned_data.get("entries_per_day") or 5
        return max(5, min(value, 25))

    class Meta:
        model = Timesheet
        fields = ["week_start", "entries_per_day"]
        widgets = {
            "week_start": forms.DateInput(attrs={"type": "date", "class": "form-control", "min": "2024-01-07", "step": "7"}),
            "entries_per_day": forms.NumberInput(attrs={"class": "form-control", "min": "5", "max": "25"}),
        }
        help_texts = {
            "week_start": "Choose the Sunday that starts the timesheet week.",
            "entries_per_day": "Default is 5 to match the Excel template. Use more rows for web/PDF timesheets.",
        }


class TimesheetImportForm(forms.ModelForm):
    class Meta:
        model = TimesheetImport
        fields = ["uploaded_file"]
        widgets = {"uploaded_file": forms.FileInput(attrs={"class": "form-control", "accept": ".xlsx"})}


class TimesheetBulkZipImportForm(forms.Form):
    zip_file = forms.FileField(
        label="ZIP file",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".zip"}),
        help_text="Upload a ZIP file containing one or more .xlsx timesheets. Files named ~$*.xlsx are skipped.",
    )
    mark_submitted = forms.BooleanField(
        required=False,
        label="Mark imported timesheets as submitted",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Uses the current date/time as the submitted date.",
    )
    mark_approved = forms.BooleanField(
        required=False,
        label="Mark imported timesheets as approved",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Approved imports are also marked submitted first.",
    )

    def clean_zip_file(self):
        uploaded = self.cleaned_data["zip_file"]
        if not uploaded.name.lower().endswith(".zip"):
            raise forms.ValidationError("Please upload a .zip file.")
        return uploaded


class TimesheetSubmitForm(forms.Form):
    export_format = forms.ChoiceField(
        choices=Timesheet.ExportFormat.choices,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial=Timesheet.ExportFormat.EXCEL,
    )

    def __init__(self, *args, timesheet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.timesheet = timesheet
        if timesheet and not timesheet.can_export_excel:
            self.fields["export_format"].initial = Timesheet.ExportFormat.PDF
            self.fields["export_format"].choices = [(Timesheet.ExportFormat.PDF, "PDF Report")]

    def clean_export_format(self):
        export_format = self.cleaned_data["export_format"]
        if self.timesheet and export_format == Timesheet.ExportFormat.EXCEL and not self.timesheet.can_export_excel:
            raise forms.ValidationError("Excel export only works when each date has 5 or fewer time entries. Use PDF Report instead.")
        return export_format


class TimesheetDeleteForm(forms.Form):
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional reason"}),
    )


class TimesheetReopenForm(forms.Form):
    reason = forms.CharField(
        required=True,
        label="Reason for reopening",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "Example: Need to correct Thursday overtime hours.",
        }),
    )
