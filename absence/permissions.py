from accounts.models import EmployeeProfile
from timesheets.permissions import is_management_staff, is_project_manager


def can_view_absence_request(user, absence_request):
    if not user.is_authenticated:
        return False
    if absence_request.employee_id == user.id:
        return True
    if is_management_staff(user):
        return True
    return bool(is_project_manager(user) and absence_request.manager_id == user.id)


def can_supervisor_decide(user, absence_request):
    if not user.is_authenticated or absence_request.status != absence_request.Status.SUBMITTED:
        return False
    if is_management_staff(user):
        return True
    return bool(is_project_manager(user) and absence_request.manager_id == user.id)


def can_decide_exception(user, absence_request):
    return bool(
        user.is_authenticated
        and is_management_staff(user)
        and absence_request.status == absence_request.Status.PENDING_EXCEPTION
    )


def can_manage_pto_account(user, employee):
    if not user.is_authenticated:
        return False
    if is_management_staff(user):
        return True
    if not is_project_manager(user):
        return False
    profile = getattr(employee, "employee_profile", None)
    return bool(profile and profile.supervisor_id == user.id)


def can_import_pto(user):
    return bool(user.is_authenticated and is_management_staff(user))


def employees_manageable_by(user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not user.is_authenticated:
        return User.objects.none()
    if is_management_staff(user):
        return User.objects.filter(is_active=True, employee_profile__isnull=False).order_by("last_name", "first_name", "username")
    if not is_project_manager(user):
        return User.objects.none()
    return User.objects.filter(
        is_active=True,
        employee_profile__supervisor=user,
    ).order_by("last_name", "first_name", "username")
