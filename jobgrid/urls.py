from django.urls import path
from . import views

app_name = "jobgrid"

urlpatterns = [
    path("", views.grid, name="grid"),
    path("api/projects/", views.project_create, name="project_create"),
    path("api/projects/<int:project_id>/", views.project_update, name="project_update"),
    path("api/projects/<int:project_id>/data/", views.project_data, name="project_data"),
    path("api/projects/<int:project_id>/tasks/", views.task_create, name="task_create"),
    path("api/projects/<int:project_id>/reorder/", views.task_reorder, name="task_reorder"),
    path("api/tasks/<int:task_id>/", views.task_update, name="task_update"),
    path("api/tasks/<int:task_id>/duplicate/", views.task_duplicate, name="task_duplicate"),
    path("api/tasks/<int:task_id>/delete/", views.task_delete, name="task_delete"),
]
