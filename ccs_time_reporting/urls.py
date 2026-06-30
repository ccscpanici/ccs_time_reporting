from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='timesheet_list', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('accounts.urls')),
    path('timesheets/', include('timesheets.urls')),
    path('reports/', include('reports.urls')), 
    path('jobgrid/', include('jobgrid.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
