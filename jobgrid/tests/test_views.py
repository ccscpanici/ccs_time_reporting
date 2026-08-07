import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from jobgrid.models import JobGridProject, JobGridTask
from jobgrid.views import (
    _parse_date,
    _payload,
    _task_to_dict,
    _tree_for_project,
    is_project_manager,
)
from timesheets.tests.base import AppTestCase


class JobGridTestBase(AppTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = cls.make_user(username="grid_employee")
        cls.manager = cls.make_user(username="grid_manager")
        cls.management = cls.make_user(username="grid_management")
        cls.superuser = cls.make_user(username="grid_admin", is_superuser=True, is_staff=True)
        cls.add_to_group(cls.manager, "ProjectManagers")
        cls.add_to_group(cls.management, "Management")

    def make_project(self, **overrides):
        values = {
            "name": "Test Project",
            "customer": "Test Customer",
            "job_number": "26001",
            "is_active": True,
            "sort_order": 10,
        }
        values.update(overrides)
        return JobGridProject.objects.create(**values)

    def make_task(self, *, project, **overrides):
        values = {
            "task_name": "Test Task",
            "sort_order": 10,
            "created_by": self.manager,
        }
        values.update(overrides)
        return JobGridTask.objects.create(project=project, **values)

    def json_request(self, method, url, payload=None):
        return getattr(self.client, method)(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )


class JobGridHelperTests(TestCase):
    def test_is_project_manager_accepts_expected_users(self):
        user_model = JobGridTask._meta.get_field("created_by").remote_field.model
        regular = user_model.objects.create_user(username="regular")
        manager = user_model.objects.create_user(username="manager")
        management = user_model.objects.create_user(username="management")
        superuser = user_model.objects.create_superuser(username="super", email="super@example.com", password="pw")
        from django.contrib.auth.models import Group

        manager.groups.add(Group.objects.get_or_create(name="ProjectManagers")[0])
        management.groups.add(Group.objects.get_or_create(name="Management")[0])

        self.assertFalse(is_project_manager(regular))
        self.assertTrue(is_project_manager(manager))
        self.assertTrue(is_project_manager(management))
        self.assertTrue(is_project_manager(superuser))

    def test_parse_date_accepts_iso_and_rejects_invalid(self):
        self.assertEqual(_parse_date("2026-08-06"), date(2026, 8, 6))
        self.assertIsNone(_parse_date(""))
        self.assertIsNone(_parse_date(None))
        self.assertIsNone(_parse_date("08/06/2026"))
        self.assertIsNone(_parse_date(123))

    def test_payload_returns_object_or_empty_dict(self):
        class Request:
            body = b'{"name": "Grid"}'

        self.assertEqual(_payload(Request()), {"name": "Grid"})
        Request.body = b""
        self.assertEqual(_payload(Request()), {})
        Request.body = b"not-json"
        self.assertEqual(_payload(Request()), {})

    def test_task_to_dict_serializes_dates_and_relationships(self):
        user_model = JobGridTask._meta.get_field("created_by").remote_field.model
        user = user_model.objects.create_user(username="owner")
        project = JobGridProject.objects.create(name="Project")
        parent = JobGridTask.objects.create(project=project, task_name="Parent", sort_order=10, created_by=user)
        task = JobGridTask.objects.create(
            project=project,
            parent=parent,
            task_name="Child",
            start=date(2026, 8, 1),
            finish=date(2026, 8, 2),
            duration="2d",
            predecessors="1",
            assigned_to="Chris",
            percent_complete=50,
            status=JobGridTask.STATUS_IN_PROGRESS,
            comments="Working",
            is_group=True,
            sort_order=20,
            created_by=user,
        )

        data = _task_to_dict(task)

        self.assertEqual(data["id"], task.id)
        self.assertEqual(data["start"], "2026-08-01")
        self.assertEqual(data["finish"], "2026-08-02")
        self.assertEqual(data["parent_id"], parent.id)
        self.assertEqual(data["_children"], [])

    def test_tree_for_project_builds_nested_rows_and_orphans_as_roots(self):
        project = JobGridProject.objects.create(name="Project")
        other = JobGridProject.objects.create(name="Other")
        parent = JobGridTask.objects.create(project=project, task_name="Parent", sort_order=10)
        child = JobGridTask.objects.create(project=project, parent=parent, task_name="Child", sort_order=20)
        orphan_parent = JobGridTask.objects.create(project=other, task_name="Other Parent", sort_order=10)
        orphan = JobGridTask.objects.create(project=project, task_name="Orphan", sort_order=30)
        JobGridTask.objects.filter(pk=orphan.pk).update(parent_id=orphan_parent.pk)

        rows = _tree_for_project(project)

        self.assertEqual([row["task_name"] for row in rows], ["Parent", "Orphan"])
        self.assertEqual(rows[0]["_children"][0]["id"], child.id)


class JobGridPermissionAndMethodTests(JobGridTestBase):
    def test_anonymous_user_is_redirected_from_every_endpoint(self):
        project = self.make_project()
        task = self.make_task(project=project)
        endpoints = [
            ("get", reverse("jobgrid:grid")),
            ("get", reverse("jobgrid:project_data", args=[project.pk])),
            ("post", reverse("jobgrid:project_create")),
            ("patch", reverse("jobgrid:project_update", args=[project.pk])),
            ("post", reverse("jobgrid:task_create", args=[project.pk])),
            ("patch", reverse("jobgrid:task_update", args=[task.pk])),
            ("post", reverse("jobgrid:task_duplicate", args=[task.pk])),
            ("post", reverse("jobgrid:task_delete", args=[task.pk])),
            ("post", reverse("jobgrid:task_reorder", args=[project.pk])),
        ]

        for method, url in endpoints:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, content_type="application/json")
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)

    def test_authenticated_non_manager_is_redirected_from_grid(self):
        self.login(self.employee)
        url = reverse("jobgrid:grid")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertIn("next=", response.url)

    def test_project_manager_management_and_superuser_can_open_grid(self):
        for user in [self.manager, self.management, self.superuser]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("jobgrid:grid")).status_code, 200)

    def test_endpoints_enforce_post_and_patch_methods(self):
        project = self.make_project()
        task = self.make_task(project=project)
        self.login(self.manager)

        self.assertEqual(self.client.get(reverse("jobgrid:project_create")).status_code, 405)
        self.assertEqual(self.client.post(reverse("jobgrid:project_update", args=[project.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("jobgrid:task_create", args=[project.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("jobgrid:task_update", args=[task.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("jobgrid:task_duplicate", args=[task.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("jobgrid:task_delete", args=[task.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("jobgrid:task_reorder", args=[project.pk])).status_code, 405)


class JobGridPageAndProjectTests(JobGridTestBase):
    def test_grid_uses_first_active_project_by_sort_order(self):
        later = self.make_project(name="Later", sort_order=20)
        first = self.make_project(name="First", job_number="26002", sort_order=10)
        self.make_project(name="Inactive", job_number="26003", is_active=False, sort_order=0)
        self.login(self.manager)

        response = self.client.get(reverse("jobgrid:grid"))

        self.assertEqual(response.context["project"], first)
        self.assertEqual(list(response.context["projects"]), [first, later])
        self.assertEqual(response.context["statuses"], [choice[0] for choice in JobGridTask.STATUS_CHOICES])

    def test_grid_creates_demo_project_when_no_active_projects_exist(self):
        self.login(self.manager)

        response = self.client.get(reverse("jobgrid:grid"))

        project = JobGridProject.objects.get(name="Saputo")
        self.assertEqual(response.context["project"], project)
        self.assertTrue(project.tasks.exists())
        self.assertTrue(project.tasks.filter(task_name="Waupun", is_group=True).exists())
        self.assertTrue(project.tasks.filter(task_name="Project Activation Complete", status=JobGridTask.STATUS_COMPLETE).exists())
        self.assertTrue(project.tasks.filter(created_by=self.manager).exists())

    def test_project_data_returns_nested_tree(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent", is_group=True, sort_order=10)
        child = self.make_task(project=project, parent=parent, task_name="Child", sort_order=20)
        self.login(self.manager)

        response = self.client.get(reverse("jobgrid:project_data", args=[project.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["project"], {"id": project.id, "name": project.name})
        self.assertEqual(payload["rows"][0]["id"], parent.id)
        self.assertEqual(payload["rows"][0]["_children"][0]["id"], child.id)

    def test_project_data_missing_project_returns_404(self):
        self.login(self.manager)
        self.assertEqual(self.client.get(reverse("jobgrid:project_data", args=[999999])).status_code, 404)

    def test_project_create_trims_fields_and_assigns_sort_order(self):
        self.make_project(name="Existing", sort_order=50)
        self.login(self.manager)

        response = self.json_request(
            "post",
            reverse("jobgrid:project_create"),
            {"name": "  New Project  ", "customer": "  Acme  ", "job_number": " 26010 "},
        )

        project = JobGridProject.objects.get(name="New Project")
        self.assertEqual(project.customer, "Acme")
        self.assertEqual(project.job_number, "26010")
        self.assertEqual(project.sort_order, 10)
        self.assertEqual(response.json(), {"ok": True, "project_id": project.id, "project_name": "New Project"})

    def test_project_create_uses_default_for_blank_or_invalid_json(self):
        self.login(self.manager)

        blank = self.json_request("post", reverse("jobgrid:project_create"), {"name": "   "})
        invalid = self.client.post(reverse("jobgrid:project_create"), data="not-json", content_type="application/json")

        self.assertEqual(blank.status_code, 200)
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(JobGridProject.objects.filter(name="New Project").count(), 2)

    def test_project_update_changes_only_supplied_fields(self):
        project = self.make_project(name="Old", customer="Old Customer", job_number="26001")
        self.login(self.manager)

        response = self.json_request(
            "patch",
            reverse("jobgrid:project_update", args=[project.pk]),
            {"name": " Updated ", "customer": None},
        )

        project.refresh_from_db()
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(project.name, "Updated")
        self.assertEqual(project.customer, "")
        self.assertEqual(project.job_number, "26001")

    def test_project_update_missing_project_returns_404(self):
        self.login(self.manager)
        response = self.json_request("patch", reverse("jobgrid:project_update", args=[999999]), {"name": "X"})
        self.assertEqual(response.status_code, 404)


class JobGridTaskCreateUpdateTests(JobGridTestBase):
    def test_task_create_defaults_and_appends_after_max_order(self):
        project = self.make_project()
        self.make_task(project=project, sort_order=30)
        self.login(self.manager)

        response = self.json_request("post", reverse("jobgrid:task_create", args=[project.pk]), {})

        task = JobGridTask.objects.get(pk=response.json()["task"]["id"])
        self.assertEqual(task.task_name, "New Task")
        self.assertEqual(task.sort_order, 40)
        self.assertEqual(task.created_by, self.manager)
        self.assertIsNone(task.parent)

    def test_task_create_supports_parent_group_and_after_task(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent", sort_order=10)
        after = self.make_task(project=project, task_name="After", sort_order=20)
        self.login(self.manager)

        response = self.json_request(
            "post",
            reverse("jobgrid:task_create", args=[project.pk]),
            {"task_name": "  Child Group  ", "parent_id": parent.id, "after_task_id": after.id, "is_group": True},
        )

        task = JobGridTask.objects.get(pk=response.json()["task"]["id"])
        self.assertEqual(task.task_name, "Child Group")
        self.assertEqual(task.parent, parent)
        self.assertTrue(task.is_group)
        self.assertEqual(task.sort_order, 21)

    def test_task_create_ignores_parent_and_after_task_from_other_project(self):
        project = self.make_project()
        other = self.make_project(name="Other", job_number="26002")
        foreign_parent = self.make_task(project=other, task_name="Foreign Parent")
        foreign_after = self.make_task(project=other, task_name="Foreign After", sort_order=80)
        self.login(self.manager)

        response = self.json_request(
            "post",
            reverse("jobgrid:task_create", args=[project.pk]),
            {"parent_id": foreign_parent.id, "after_task_id": foreign_after.id},
        )

        task = JobGridTask.objects.get(pk=response.json()["task"]["id"])
        self.assertIsNone(task.parent)
        self.assertEqual(task.sort_order, 10)

    def test_task_create_missing_project_returns_404(self):
        self.login(self.manager)
        response = self.json_request("post", reverse("jobgrid:task_create", args=[999999]), {})
        self.assertEqual(response.status_code, 404)

    def test_task_update_updates_editable_dates_percent_parent_and_order(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent", sort_order=10)
        task = self.make_task(project=project, task_name="Original", sort_order=20)
        self.login(self.manager)

        response = self.json_request(
            "patch",
            reverse("jobgrid:task_update", args=[task.pk]),
            {
                "task_name": " Updated Task ",
                "duration": " 3d ",
                "predecessors": " 1,2 ",
                "assigned_to": " Chris ",
                "status": JobGridTask.STATUS_IN_PROGRESS,
                "comments": " Notes ",
                "is_group": True,
                "start": "2026-08-01",
                "finish": "2026-08-03",
                "percent_complete": 140,
                "parent_id": parent.id,
                "sort_order": "35",
            },
        )

        task.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(task.task_name, "Updated Task")
        self.assertEqual(task.duration, "3d")
        self.assertEqual(task.predecessors, "1,2")
        self.assertEqual(task.assigned_to, "Chris")
        self.assertEqual(task.comments, "Notes")
        self.assertTrue(task.is_group)
        self.assertEqual(task.start, date(2026, 8, 1))
        self.assertEqual(task.finish, date(2026, 8, 3))
        self.assertEqual(task.percent_complete, 100)
        self.assertEqual(task.parent, parent)
        self.assertEqual(task.sort_order, 35)

    def test_task_update_handles_invalid_values_and_can_clear_parent(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent", sort_order=10)
        task = self.make_task(
            project=project,
            parent=parent,
            task_name="Task",
            start=date(2026, 8, 1),
            finish=date(2026, 8, 2),
            percent_complete=75,
            sort_order=20,
        )
        self.login(self.manager)

        self.json_request(
            "patch",
            reverse("jobgrid:task_update", args=[task.pk]),
            {"start": "bad", "finish": "", "percent_complete": "bad", "parent_id": None, "sort_order": "bad"},
        )

        task.refresh_from_db()
        self.assertIsNone(task.start)
        self.assertIsNone(task.finish)
        self.assertEqual(task.percent_complete, 0)
        self.assertIsNone(task.parent)
        self.assertEqual(task.sort_order, 20)

    def test_task_update_prevents_self_parent_and_foreign_parent(self):
        project = self.make_project()
        other = self.make_project(name="Other", job_number="26002")
        task = self.make_task(project=project)
        foreign = self.make_task(project=other)
        self.login(self.manager)

        self.json_request("patch", reverse("jobgrid:task_update", args=[task.pk]), {"parent_id": task.id})
        task.refresh_from_db()
        self.assertIsNone(task.parent)

        self.json_request("patch", reverse("jobgrid:task_update", args=[task.pk]), {"parent_id": foreign.id})
        task.refresh_from_db()
        self.assertIsNone(task.parent)

    def test_task_update_clamps_negative_percent_to_zero(self):
        project = self.make_project()
        task = self.make_task(project=project, percent_complete=50)
        self.login(self.manager)

        self.json_request("patch", reverse("jobgrid:task_update", args=[task.pk]), {"percent_complete": -12})

        task.refresh_from_db()
        self.assertEqual(task.percent_complete, 0)

    def test_task_update_missing_task_returns_404(self):
        self.login(self.manager)
        response = self.json_request("patch", reverse("jobgrid:task_update", args=[999999]), {})
        self.assertEqual(response.status_code, 404)


class JobGridTaskDuplicateDeleteReorderTests(JobGridTestBase):
    def test_task_duplicate_copies_fields_changes_name_order_and_creator(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent", sort_order=10)
        source = self.make_task(
            project=project,
            parent=parent,
            task_name="Original",
            assigned_to="Chris",
            comments="Keep",
            percent_complete=60,
            sort_order=20,
            created_by=self.employee,
        )
        self.login(self.manager)

        response = self.client.post(reverse("jobgrid:task_duplicate", args=[source.pk]))

        duplicate = JobGridTask.objects.exclude(pk=source.pk).get(task_name="Original Copy")
        self.assertEqual(duplicate.project, project)
        self.assertEqual(duplicate.parent, parent)
        self.assertEqual(duplicate.assigned_to, "Chris")
        self.assertEqual(duplicate.comments, "Keep")
        self.assertEqual(duplicate.percent_complete, 60)
        self.assertEqual(duplicate.sort_order, 21)
        self.assertEqual(duplicate.created_by, self.manager)
        self.assertEqual(response.json()["task"]["id"], duplicate.id)

    def test_task_duplicate_missing_task_returns_404(self):
        self.login(self.manager)
        self.assertEqual(self.client.post(reverse("jobgrid:task_duplicate", args=[999999])).status_code, 404)

    def test_task_delete_removes_task_and_descendants(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent")
        child = self.make_task(project=project, parent=parent, task_name="Child", sort_order=20)
        self.login(self.manager)

        response = self.client.post(reverse("jobgrid:task_delete", args=[parent.pk]))

        self.assertEqual(response.json(), {"ok": True})
        self.assertFalse(JobGridTask.objects.filter(pk__in=[parent.pk, child.pk]).exists())

    def test_task_delete_missing_task_returns_404(self):
        self.login(self.manager)
        self.assertEqual(self.client.post(reverse("jobgrid:task_delete", args=[999999])).status_code, 404)

    def test_task_reorder_updates_valid_rows_and_skips_invalid_rows(self):
        project = self.make_project()
        parent = self.make_task(project=project, task_name="Parent", sort_order=10)
        first = self.make_task(project=project, task_name="First", sort_order=20)
        second = self.make_task(project=project, task_name="Second", sort_order=30)
        other = self.make_project(name="Other", job_number="26002")
        foreign = self.make_task(project=other, task_name="Foreign", sort_order=10)
        self.login(self.manager)

        response = self.json_request(
            "post",
            reverse("jobgrid:task_reorder", args=[project.pk]),
            {
                "rows": [
                    {"id": first.id, "sort_order": 5, "parent_id": parent.id},
                    {"id": second.id, "sort_order": "bad", "parent_id": None},
                    {"id": foreign.id, "sort_order": 1, "parent_id": None},
                    {"id": 999999, "sort_order": 1, "parent_id": None},
                    {"id": None, "sort_order": 1, "parent_id": None},
                ]
            },
        )

        first.refresh_from_db()
        second.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(first.sort_order, 5)
        self.assertEqual(first.parent, parent)
        self.assertEqual(second.sort_order, 30)
        self.assertEqual(foreign.sort_order, 10)

    def test_task_reorder_prevents_self_or_foreign_parent_and_can_clear_parent(self):
        project = self.make_project()
        other = self.make_project(name="Other", job_number="26002")
        task = self.make_task(project=project, sort_order=10)
        foreign_parent = self.make_task(project=other, sort_order=10)
        self.login(self.manager)

        self.json_request(
            "post",
            reverse("jobgrid:task_reorder", args=[project.pk]),
            {"rows": [{"id": task.id, "sort_order": 15, "parent_id": task.id}]},
        )
        task.refresh_from_db()
        self.assertIsNone(task.parent)

        self.json_request(
            "post",
            reverse("jobgrid:task_reorder", args=[project.pk]),
            {"rows": [{"id": task.id, "sort_order": 20, "parent_id": foreign_parent.id}]},
        )
        task.refresh_from_db()
        self.assertIsNone(task.parent)

        parent = self.make_task(project=project, task_name="Parent", sort_order=30)
        task.parent = parent
        task.save(update_fields=["parent"])
        self.json_request(
            "post",
            reverse("jobgrid:task_reorder", args=[project.pk]),
            {"rows": [{"id": task.id, "sort_order": 25, "parent_id": None}]},
        )
        task.refresh_from_db()
        self.assertIsNone(task.parent)

    def test_task_reorder_invalid_json_is_noop_success(self):
        project = self.make_project()
        task = self.make_task(project=project, sort_order=10)
        self.login(self.manager)

        response = self.client.post(
            reverse("jobgrid:task_reorder", args=[project.pk]),
            data="not-json",
            content_type="application/json",
        )

        task.refresh_from_db()
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(task.sort_order, 10)

    def test_task_reorder_missing_project_returns_404(self):
        self.login(self.manager)
        response = self.json_request("post", reverse("jobgrid:task_reorder", args=[999999]), {"rows": []})
        self.assertEqual(response.status_code, 404)
