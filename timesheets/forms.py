from datetime import date, timedelta
from django import forms
from .models import ActiveProject, Customer, Job, JobListImport, Timesheet, TimesheetImport


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




class JobListImportForm(forms.ModelForm):
    class Meta:
        model = JobListImport
        fields = ["uploaded_file"]
        widgets = {
            "uploaded_file": forms.FileInput(attrs={"class": "form-control", "accept": ".xlsx"})
        }
        labels = {"uploaded_file": "Job List Excel File"}
        help_texts = {"uploaded_file": "Download the SharePoint job list as .xlsx, then upload it here."}

    def clean_uploaded_file(self):
        uploaded = self.cleaned_data["uploaded_file"]
        if not uploaded.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Please upload an .xlsx file.")
        return uploaded


class JobForm(forms.ModelForm):
    customer_name = forms.CharField(
        required=False,
        label="Customer",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Customer name"}),
        help_text="Entering a new customer name will create that customer automatically.",
    )
    job_status = forms.ChoiceField(
        choices=Job.JOB_STATUS_CHOICES,
        initial=Job.STATUS_UNKNOWN,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    invoice_status = forms.ChoiceField(
        required=False,
        choices=Job.INVOICE_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Job
        fields = [
            "job_number",
            "description",
            "customer_name",
            "year",
            "job_month",
            "job_status",
            "invoice_status",
            "work_type",
            "location",
            "customer_contact",
            "customer_po",
            "lead",
            "lead_user",
            "quote_number",
            "comments",
            "engineer_01",
            "engineer_01_user",
            "engineer_02",
            "engineer_02_user",
            "engineer_03",
            "engineer_03_user",
            "engineer_04",
            "engineer_04_user",
            "engineer_05",
            "engineer_05_user",
            "engineer_06",
            "engineer_06_user",
            "engineer_07",
            "engineer_07_user",
            "engineer_08",
            "engineer_08_user",
            "engineer_09",
            "engineer_09_user",
            "engineer_10",
            "engineer_10_user",
            "active",
        ]
        labels = {"active": "Available for Time Entry", "job_month": "Month"}
        widgets = {
            "job_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Example: 250745-151"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "year": forms.NumberInput(attrs={"class": "form-control", "min": "2000", "max": "2099"}),
            "job_month": forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "12"}),
            "work_type": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "customer_contact": forms.TextInput(attrs={"class": "form-control"}),
            "customer_po": forms.TextInput(attrs={"class": "form-control"}),
            "lead": forms.TextInput(attrs={"class": "form-control"}),
            "lead_user": forms.Select(attrs={"class": "form-select"}),
            "quote_number": forms.TextInput(attrs={"class": "form-control"}),
            "comments": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "engineer_01": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_01_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_02": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_02_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_03": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_03_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_04": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_04_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_05": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_05_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_06": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_06_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_07": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_07_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_08": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_08_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_09": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_09_user": forms.Select(attrs={"class": "form-select"}),
            "engineer_10": forms.TextInput(attrs={"class": "form-control"}),
            "engineer_10_user": forms.Select(attrs={"class": "form-select"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "year": "Used for sorting/filtering the Job List. Leave blank to infer from the job number when possible.",
            "job_month": "Optional. Support jobs like SCL2603 infer month 3.",
            "job_status": "Blank statuses are saved as Unknown Status. Warning statuses are allowed for time entry but show a warning to users.",
            "active": "Checked jobs are available in Project / Job selectors and Excel import corrections. Unchecked jobs remain available for historical reporting only.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_fields = ["lead_user"] + [f"engineer_{idx:02d}_user" for idx in range(1, 11)]
        for field_name in user_fields:
            if field_name in self.fields:
                self.fields[field_name].queryset = self.fields[field_name].queryset.order_by("first_name", "last_name", "username")
        if self.instance and self.instance.pk and self.instance.customer:
            self.fields["customer_name"].initial = self.instance.customer.name

    def clean_job_number(self):
        job_number = (self.cleaned_data.get("job_number") or "").strip()
        if not job_number:
            raise forms.ValidationError("Job number is required.")

        qs = Job.objects.filter(job_number__iexact=job_number)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A job with this job number already exists.")
        return job_number

    def clean_job_status(self):
        return (self.cleaned_data.get("job_status") or Job.STATUS_UNKNOWN).strip() or Job.STATUS_UNKNOWN

    def save(self, commit=True):
        job = super().save(commit=False)
        customer_name = (self.cleaned_data.get("customer_name") or "").strip()
        if customer_name:
            customer, _created = Customer.objects.get_or_create(name=customer_name)
            job.customer = customer
        else:
            job.customer = None
        if commit:
            job.save()
            self.save_m2m()
        return job

class TimesheetBulkZipImportForm(forms.Form):
    zip_file = forms.FileField(
        label="ZIP file",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".zip"}),
        help_text="Upload a ZIP file containing one or more .xlsx timesheets. Files named ~$*.xlsx are skipped. Browser uploads are limited to 100MB; use the server import command for larger ZIP files.",
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


class TimesheetRejectForm(forms.Form):
    reason = forms.CharField(
        required=True,
        label="Rejection notes",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "Explain what needs to be corrected before this timesheet can be approved.",
        }),
    )


class ActiveProjectForm(forms.ModelForm):
    class Meta:
        model = ActiveProject
        fields = ["job_number", "budgeted_hours", "active"]
        labels = {"active": "Available for Time Entry", "job_number": "Job Number"}
        widgets = {
            "job_number": forms.TextInput(attrs={
                "class": "form-control",
                "list": "active-project-job-options",
                "autocomplete": "off",
                "placeholder": "Start typing a valid job number...",
            }),
            "budgeted_hours": forms.NumberInput(attrs={"class": "form-control", "step": "0.25", "min": "0"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "job_number": "Select an available job from the job list. Active projects can only be created for valid time-entry jobs.",
        }

    def clean_job_number(self):
        job_number = (self.cleaned_data.get("job_number") or "").strip()
        if not job_number:
            raise forms.ValidationError("Job number is required.")

        job = Job.objects.filter(active=True, job_number__iexact=job_number).exclude(description="").first()
        if not job:
            raise forms.ValidationError("Select a valid active job from the job list.")

        qs = ActiveProject.objects.filter(active=True, job_number__iexact=job.job_number)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This job is already on the Active Projects list.")

        return job.job_number
