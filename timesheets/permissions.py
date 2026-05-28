
def is_management_staff(user):
    return bool(
        user.is_authenticated
        and (user.is_superuser or user.groups.filter(name="Management Staff").exists())
    )


def is_project_manager(user):
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__in=["Management Staff", "ProjectManagers"]).exists()
        )
    )


def is_assigned_project_manager(user, timesheet):
    if not user.is_authenticated:
        return False
    if not is_project_manager(user):
        return False
    profile = getattr(timesheet.employee, "employee_profile", None)
    return bool(profile and profile.supervisor_id == user.id)


def can_view_timesheet(user, timesheet):
    if not user.is_authenticated:
        return False
    return bool(
        timesheet.employee_id == user.id
        or is_management_staff(user)
        or is_assigned_project_manager(user, timesheet)
    )


def can_approve_timesheet(user, timesheet):
   if not user.is_authenticated:
        return False

   if is_management_staff(user):
        return True

   if is_assigned_project_manager(user, timesheet):
        return True

   employee_profile = getattr(timesheet.employee, "employee_profile", None)

   if (
        is_project_manager(user)
        and timesheet.employee_id == user.id
        and employee_profile
        and employee_profile.supervisor_id is None
   ):
        return True

   return False
# end can_approve_timesheet
