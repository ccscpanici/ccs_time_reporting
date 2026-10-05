"""Application support code for forms."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import EmployeeProfile, OfficeLocation, UserPreference


class UserPreferenceForm(forms.ModelForm):
    """Provide user preference form behavior for this module."""
    class Meta:
        """Provide meta behavior for this module."""
        model = UserPreference
        fields = ["color_scheme", "theme"]
        widgets = {
            "color_scheme": forms.Select(attrs={"class": "form-select"}),
            "theme": forms.Select(attrs={"class": "form-select"}),
        }


class UserProfileForm(forms.ModelForm):
    """Provide user profile form behavior for this module."""
    class Meta:
        """Provide meta behavior for this module."""
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class EmployeeProfileForm(forms.ModelForm):
    """Provide employee profile form behavior for this module."""
    office_location = forms.ModelChoiceField(
        queryset=OfficeLocation.objects.filter(active=True).order_by("name"),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        """Provide meta behavior for this module."""
        model = EmployeeProfile
        fields = [
            "office_location",
            "address_1",
            "address_2",
            "city",
            "state",
            "postal_code",
        ]
        widgets = {
            "address_1": forms.TextInput(attrs={"class": "form-control"}),
            "address_2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
        }


class UserSignupForm(UserCreationForm):
    """Provide user signup form behavior for this module."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        help_text="You must use your @gotoccs.com email address.",
    )
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        """Provide meta behavior for this module."""
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        """Provide the clean email operation for this module."""
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email.endswith("@gotoccs.com"):
            raise forms.ValidationError("You must use a @gotoccs.com email address to sign up.")

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")

        return email

    def save(self, commit=True):
        """Provide the save operation for this module."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        if commit:
            user.save()

        return user
