from .models import UserPreference

def user_preferences(request):
    if not request.user.is_authenticated:
        return {'ui_preferences': None}
    prefs, _ = UserPreference.objects.get_or_create(user=request.user)
    return {'ui_preferences': prefs}


from timesheets.permissions import is_management_staff, is_project_manager


def management_context(request):
    return {
        "is_management_staff": is_management_staff(request.user) if hasattr(request, "user") else False,
        "is_project_manager": is_project_manager(request.user) if hasattr(request, "user") else False,
    }
