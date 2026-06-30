from django.contrib import admin
from .models import JobGridProject, JobGridTask


class JobGridTaskInline(admin.TabularInline):
    model = JobGridTask
    extra = 0
    fields = ("task_name", "parent", "assigned_to", "start", "finish", "percent_complete", "status", "is_group", "sort_order")


@admin.register(JobGridProject)
class JobGridProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "job_number", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "customer", "job_number")
    ordering = ("sort_order", "name")
    inlines = [JobGridTaskInline]


@admin.register(JobGridTask)
class JobGridTaskAdmin(admin.ModelAdmin):
    list_display = ("task_name", "project", "parent", "assigned_to", "percent_complete", "status", "sort_order")
    list_filter = ("project", "status", "is_group")
    search_fields = ("task_name", "assigned_to", "comments")
    ordering = ("project", "sort_order", "id")
