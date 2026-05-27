from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import EmployeeProfileForm, UserPreferenceForm, UserProfileForm, UserSignupForm
from .models import EmployeeProfile, OfficeLocation, UserPreference


@login_required
def preferences(request):
    prefs, _ = UserPreference.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = UserPreferenceForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, "Preferences saved.")
            return redirect("preferences")
    else:
        form = UserPreferenceForm(instance=prefs)
    return render(request, "accounts/preferences.html", {"form": form})


@login_required
def profile(request):
    default_office = OfficeLocation.objects.filter(active=True).order_by("name").first()
    employee_profile, _ = EmployeeProfile.objects.get_or_create(
        user=request.user,
        defaults={"office_location": default_office},
    )

    if request.method == "POST":
        user_form = UserProfileForm(request.POST, instance=request.user)
        employee_form = EmployeeProfileForm(request.POST, instance=employee_profile)

        if user_form.is_valid() and employee_form.is_valid():
            user_form.save()
            employee_form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        user_form = UserProfileForm(instance=request.user)
        employee_form = EmployeeProfileForm(instance=employee_profile)

    return render(
        request,
        "accounts/profile.html",
        {
            "user_form": user_form,
            "employee_form": employee_form,
            "employee_profile": employee_profile,
        },
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect("timesheet_list")

    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()

            default_office = OfficeLocation.objects.filter(active=True).order_by("name").first()
            EmployeeProfile.objects.get_or_create(
                user=user,
                defaults={"office_location": default_office},
            )

            login(request, user)
            messages.success(request, "Account created. Please complete your profile.")
            return redirect("profile")
    else:
        form = UserSignupForm()

    return render(request, "accounts/signup.html", {"form": form})
