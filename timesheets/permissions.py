
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
