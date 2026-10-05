"""Application support code for context processors."""

from .models import UserPreference

def user_preferences(request):
    """Provide the user preferences operation for this module."""
    if not request.user.is_authenticated:
        return {'ui_preferences': None}
    prefs, _ = UserPreference.objects.get_or_create(user=request.user)
    return {'ui_preferences': prefs}


from timesheets.permissions import is_business_admin, is_management_staff, is_project_manager


def management_context(request):
    """Provide the management context operation for this module."""
    return {
        "is_business_admin": is_business_admin(request.user) if hasattr(request, "user") else False,
        "is_management_staff": is_management_staff(request.user) if hasattr(request, "user") else False,
        "is_project_manager": is_project_manager(request.user) if hasattr(request, "user") else False,
    }
