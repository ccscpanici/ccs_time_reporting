from __future__ import annotations

from django import forms
from django.utils import timezone

from absence.models import AbsenceRequest, PTOAccount
from absence.services.pto_balances import vacation_summary
from absence.services.request_days import parse_daily_hours
from absence.services.time_values import format_hhmm, is_full_employment_week_range, parse_hhmm


class DateInput(forms.DateInput):
    input_type = "date"


class AbsenceRequestForm(forms.ModelForm):
    class Meta:
        model = AbsenceRequest
        fields = (
            "absence_type",
            "start_date",
            "end_date",
            "calendar_acknowledged",
            "negative_balance_acknowledged",
            "unpaid_start_date",
            "unpaid_end_date",
        )
        widgets = {
            "start_date": DateInput(),
            "end_date": DateInput(),
            "unpaid_start_date": DateInput(),
            "unpaid_end_date": DateInput(),
        }
        labels = {
            "calendar_acknowledged": "Vacation has been added to the company Outlook calendar",
            "negative_balance_acknowledged": "I acknowledge that this request would exceed the allowable -40:00 vacation balance",
            "unpaid_start_date": "Unpaid week starts",
            "unpaid_end_date": "Unpaid week ends",
        }

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")
        self.fields["absence_type"].widget.attrs["class"] = "form-select"
        self.fields["negative_balance_acknowledged"].required = False
        self.fields["unpaid_start_date"].required = False
        self.fields["unpaid_end_date"].required = False
        self.fields["calendar_acknowledged"].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        absence_type = cleaned.get("absence_type")
        if start and end and end < start:
            self.add_error("end_date", "End date must be on or after the first date of absence.")
            return cleaned

        if absence_type == AbsenceRequest.AbsenceType.VACATION and not cleaned.get("calendar_acknowledged"):
            self.add_error("calendar_acknowledged", "Confirm that the vacation has been added to the company Outlook calendar.")

        daily_values = None
        if start and end and end >= start:
            try:
                daily_values = parse_daily_hours(self.data, start, end)
            except ValueError as exc:
                raise forms.ValidationError(str(exc))

        if self.employee and daily_values is not None and absence_type == AbsenceRequest.AbsenceType.VACATION:
            account = PTOAccount.objects.filter(employee=self.employee).first()
            current_projected = vacation_summary(account).projected_vacation_balance_minutes if account else 0
            requested = sum(minutes for _, minutes in daily_values)
            projected = current_projected - requested
            if projected < AbsenceRequest.MIN_VACATION_BALANCE_MINUTES:
                if not cleaned.get("negative_balance_acknowledged"):
                    self.add_error("negative_balance_acknowledged", "Acknowledgment is required because the projected vacation balance is below -40:00.")
                unpaid_start = cleaned.get("unpaid_start_date")
                unpaid_end = cleaned.get("unpaid_end_date")
                if not is_full_employment_week_range(unpaid_start, unpaid_end):
                    self.add_error("unpaid_start_date", "Negative-balance exceptions require complete Monday-through-Friday employment week increments.")
        return cleaned


class PTOAccountForm(forms.Form):
    vacation_weeks_per_year = forms.DecimalField(min_value=0, max_digits=5, decimal_places=2, label="Vacation weeks / year")
    vacation_accrual = forms.CharField(
        label="Vacation accrual",
        help_text="Payroll report's Vacation Available value. Use HHH:MM, for example 73:01 or -26:16.",
    )
    vacation_used = forms.CharField(label="Vacation used (payroll)", help_text="Use HHH:MM.")
    sick_available = forms.CharField(
        label="Sick available (payroll)",
        help_text="Use HHH:MM. Negative values are expected in the CCS payroll report.",
    )
    sick_used = forms.CharField(label="Sick used", help_text="Use HHH:MM.")
    balance_as_of = forms.DateField(required=False, widget=DateInput())
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), help_text="Optional reason for the manual update.")

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        if account and not self.is_bound:
            self.initial.update({
                "vacation_weeks_per_year": account.vacation_weeks_per_year,
                "vacation_accrual": format_hhmm(account.vacation_accrual_minutes),
                "vacation_used": format_hhmm(account.vacation_used_minutes),
                "sick_available": format_hhmm(account.sick_available_minutes),
                "sick_used": format_hhmm(account.sick_used_minutes),
                "balance_as_of": account.balance_as_of,
            })

    def clean(self):
        cleaned = super().clean()
        for field in ("vacation_accrual", "vacation_used", "sick_available", "sick_used"):
            value = cleaned.get(field)
            if value is None:
                continue
            try:
                cleaned[f"{field}_minutes"] = parse_hhmm(value)
            except ValueError as exc:
                self.add_error(field, str(exc))
        return cleaned

    def save(self, *, updated_by):
        account = self.account
        account.vacation_weeks_per_year = self.cleaned_data["vacation_weeks_per_year"]
        account.vacation_balance_minutes = self.cleaned_data["vacation_accrual_minutes"]
        account.vacation_used_minutes = self.cleaned_data["vacation_used_minutes"]
        account.sick_balance_minutes = self.cleaned_data["sick_available_minutes"]
        account.sick_used_minutes = self.cleaned_data["sick_used_minutes"]
        account.balance_as_of = self.cleaned_data.get("balance_as_of")
        account.updated_by = updated_by
        account.save()
        return account


class PTOImportUploadForm(forms.Form):
    source_file = forms.FileField(label="Paid Time Off List PDF")

    def clean_source_file(self):
        upload = self.cleaned_data["source_file"]
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Upload the Paid Time Off List as a PDF file.")
        return upload


class DecisionForm(forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}), label="Notes")
