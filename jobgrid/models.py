from django.db import models
from django.contrib.auth import get_user_model


class JobGridProject(models.Model):
    name = models.CharField(max_length=255)
    customer = models.CharField(max_length=255, blank=True)
    job_number = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Project Planning Sheet"
        verbose_name_plural = "Project Planning Sheets"

    def __str__(self):
        return self.name


class JobGridTask(models.Model):
    STATUS_NOT_STARTED = "Not Started"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_WAITING = "Waiting"
    STATUS_COMPLETE = "Complete"
    STATUS_ON_HOLD = "On Hold"

    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, STATUS_NOT_STARTED),
        (STATUS_IN_PROGRESS, STATUS_IN_PROGRESS),
        (STATUS_WAITING, STATUS_WAITING),
        (STATUS_COMPLETE, STATUS_COMPLETE),
        (STATUS_ON_HOLD, STATUS_ON_HOLD),
    ]

    project = models.ForeignKey(JobGridProject, related_name="tasks", on_delete=models.CASCADE)
    parent = models.ForeignKey("self", related_name="children", null=True, blank=True, on_delete=models.CASCADE)
    task_name = models.CharField(max_length=255)
    start = models.DateField(null=True, blank=True)
    finish = models.DateField(null=True, blank=True)
    duration = models.CharField(max_length=50, blank=True)
    predecessors = models.CharField(max_length=255, blank=True)
    assigned_to = models.CharField(max_length=255, blank=True)
    percent_complete = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED, blank=True)
    comments = models.TextField(blank=True)
    is_group = models.BooleanField(default=False)
    is_expanded = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_by = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Project Task"
        verbose_name_plural = "Project Tasks"

    def __str__(self):
        return self.task_name
