import json
from datetime import datetime

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import JobGridProject, JobGridTask


def is_project_manager(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=["Management", "ProjectManagers"]).exists())


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _task_to_dict(task):
    return {
        "id": task.id,
        "task_name": task.task_name,
        "start": task.start.isoformat() if task.start else "",
        "finish": task.finish.isoformat() if task.finish else "",
        "duration": task.duration,
        "predecessors": task.predecessors,
        "assigned_to": task.assigned_to,
        "percent_complete": task.percent_complete,
        "status": task.status,
        "comments": task.comments,
        "is_group": task.is_group,
        "parent_id": task.parent_id,
        "sort_order": task.sort_order,
        "_children": [],
    }


def _tree_for_project(project):
    tasks = list(project.tasks.all().order_by("sort_order", "id"))
    by_id = {t.id: _task_to_dict(t) for t in tasks}
    roots = []
    for task in tasks:
        node = by_id[task.id]
        if task.parent_id and task.parent_id in by_id:
            by_id[task.parent_id]["_children"].append(node)
        else:
            roots.append(node)
    return roots


def _create_demo_project(user):
    project = JobGridProject.objects.create(name="Saputo", sort_order=0)

    def task(name, order, parent=None, group=False, start=None, finish=None, duration="", assigned="", pct=0, status=""):
        return JobGridTask.objects.create(
            project=project,
            parent=parent,
            task_name=name,
            is_group=group,
            start=_parse_date(start),
            finish=_parse_date(finish),
            duration=duration,
            assigned_to=assigned,
            percent_complete=pct,
            status=status or JobGridTask.STATUS_NOT_STARTED,
            sort_order=order,
            created_by=user,
        )

    task("Franklin", 10, group=True)
    task("Lena", 20, group=True)
    task("Reedsburg", 30, group=True)
    wau = task("Waupun", 40, group=True)
    p1 = task("25043S - Whey Plant Demo", 50, parent=wau, group=True, start="2025-08-28", finish="2025-08-28", duration="1d", pct=99)
    task("Project Activation Complete", 60, parent=p1, start="2025-08-28", finish="2025-08-28", duration="1d", pct=100, status=JobGridTask.STATUS_COMPLETE)
    acad = task("AutoCad", 70, parent=p1, group=True)
    task("Electrical Design", 80, parent=acad)
    task("Interconnects", 90, parent=acad)
    task("Drawings Released to Shop for Build", 100, parent=acad)
    eng = task("Engineering", 110, parent=p1, group=True)
    task("Parts List", 120, parent=eng)
    task("IO List (Demo)", 130, parent=eng, assigned="Chris Eichman", pct=50)
    task("IO List (Whey Cream Tanks)", 140, parent=eng, assigned="Chris Eichman", pct=90)
    task("Pincharts", 150, parent=eng)
    plc = task("PLC Programming", 160, parent=p1, group=True, pct=100)
    task("Base Logic", 170, parent=plc, assigned="Chris Eichman", pct=100)
    task("Project Related Logic (Demo)", 180, parent=plc, assigned="Chris Eichman")
    task("Project Related Logic (Whey Cream Tanks)", 190, parent=plc, assigned="Jeff Bloome")
    task("Testing", 200, parent=plc)
    hmi = task("HMI/SCADA", 210, parent=p1, group=True)
    task("Development (Whey Cream Tanks)", 220, parent=hmi, assigned="Jeff Bloome")
    task("Testing", 230, parent=hmi)
    task("Panel Testing", 240, parent=p1, group=True)
    task("25050S - Polished Water Silo Migration", 250, parent=wau, group=True, start="2026-03-19", finish="2026-03-24", duration="4d", pct=75)
    task("25068S - Whey CIP Support", 260, parent=wau, group=True, start="2025-10-21", finish="2025-10-31", duration="9d", assigned="Micah Kovatch")
    task("25081 - Niro Water Flush", 270, parent=wau, group=True, start="2025-12-10", finish="2025-12-10", duration="1d", pct=100)
    return project


@login_required
@user_passes_test(is_project_manager)
def grid(request):
    project = JobGridProject.objects.filter(is_active=True).order_by("sort_order", "name").first()
    if not project:
        project = _create_demo_project(request.user)
    return render(request, "jobgrid/grid.html", {
        "project": project,
        "projects": JobGridProject.objects.filter(is_active=True).order_by("sort_order", "name"),
        "statuses": [choice[0] for choice in JobGridTask.STATUS_CHOICES],
    })


@login_required
@user_passes_test(is_project_manager)
def project_data(request, project_id):
    project = get_object_or_404(JobGridProject, pk=project_id)
    return JsonResponse({"ok": True, "project": {"id": project.id, "name": project.name}, "rows": _tree_for_project(project)})


@login_required
@user_passes_test(is_project_manager)
@require_POST
def project_create(request):
    data = _payload(request)
    name = (data.get("name") or "New Project").strip() or "New Project"
    project = JobGridProject.objects.create(
        name=name,
        customer=(data.get("customer") or "").strip(),
        job_number=(data.get("job_number") or "").strip(),
        sort_order=JobGridProject.objects.count() * 10,
    )
    return JsonResponse({"ok": True, "project_id": project.id, "project_name": project.name})


@login_required
@user_passes_test(is_project_manager)
@require_http_methods(["PATCH"])
def project_update(request, project_id):
    project = get_object_or_404(JobGridProject, pk=project_id)
    data = _payload(request)
    for field in ["name", "customer", "job_number"]:
        if field in data:
            setattr(project, field, (data.get(field) or "").strip())
    project.save()
    return JsonResponse({"ok": True})


@login_required
@user_passes_test(is_project_manager)
@require_POST
def task_create(request, project_id):
    project = get_object_or_404(JobGridProject, pk=project_id)
    data = _payload(request)
    parent_id = data.get("parent_id")
    parent = JobGridTask.objects.filter(project=project, pk=parent_id).first() if parent_id else None
    after_task = JobGridTask.objects.filter(project=project, pk=data.get("after_task_id")).first() if data.get("after_task_id") else None
    max_order = project.tasks.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0
    sort_order = (after_task.sort_order + 1) if after_task else (max_order + 10)
    task = JobGridTask.objects.create(
        project=project,
        parent=parent,
        task_name=(data.get("task_name") or "New Task").strip() or "New Task",
        is_group=bool(data.get("is_group", False)),
        sort_order=sort_order,
        created_by=request.user,
    )
    return JsonResponse({"ok": True, "task": _task_to_dict(task)})


@login_required
@user_passes_test(is_project_manager)
@require_http_methods(["PATCH"])
def task_update(request, task_id):
    task = get_object_or_404(JobGridTask, pk=task_id)
    data = _payload(request)
    editable = ["task_name", "duration", "predecessors", "assigned_to", "status", "comments", "is_group"]
    for field in editable:
        if field in data:
            setattr(task, field, data[field] if not isinstance(data[field], str) else data[field].strip())
    if "start" in data:
        task.start = _parse_date(data.get("start"))
    if "finish" in data:
        task.finish = _parse_date(data.get("finish"))
    if "percent_complete" in data:
        try:
            task.percent_complete = max(0, min(100, int(data.get("percent_complete") or 0)))
        except (TypeError, ValueError):
            task.percent_complete = 0
    if "parent_id" in data:
        parent_id = data.get("parent_id")
        task.parent = JobGridTask.objects.filter(project=task.project, pk=parent_id).exclude(pk=task.pk).first() if parent_id else None
    if "sort_order" in data:
        try:
            task.sort_order = int(data.get("sort_order") or 0)
        except (TypeError, ValueError):
            pass
    task.save()
    return JsonResponse({"ok": True, "task": _task_to_dict(task)})


@login_required
@user_passes_test(is_project_manager)
@require_POST
def task_duplicate(request, task_id):
    source = get_object_or_404(JobGridTask, pk=task_id)
    source.pk = None
    source.task_name = f"{source.task_name} Copy"
    source.sort_order += 1
    source.created_by = request.user
    source.save()
    return JsonResponse({"ok": True, "task": _task_to_dict(source)})


@login_required
@user_passes_test(is_project_manager)
@require_POST
def task_delete(request, task_id):
    task = get_object_or_404(JobGridTask, pk=task_id)
    task.delete()
    return JsonResponse({"ok": True})


@login_required
@user_passes_test(is_project_manager)
@require_POST
def task_reorder(request, project_id):
    project = get_object_or_404(JobGridProject, pk=project_id)
    data = _payload(request)
    rows = data.get("rows", [])
    for item in rows:
        try:
            task = JobGridTask.objects.get(project=project, pk=item.get("id"))
            task.sort_order = int(item.get("sort_order") or 0)
            parent_id = item.get("parent_id")
            task.parent = JobGridTask.objects.filter(project=project, pk=parent_id).exclude(pk=task.pk).first() if parent_id else None
            task.save(update_fields=["sort_order", "parent", "updated_at"])
        except (JobGridTask.DoesNotExist, TypeError, ValueError):
            continue
    return JsonResponse({"ok": True})
