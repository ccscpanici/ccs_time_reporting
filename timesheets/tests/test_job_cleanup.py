from datetime import date

from timesheets.models import Job, TimeEntry
from timesheets.services.job_cleanup import (
    cleanup_invalid_job,
    entries_for_invalid_job,
    invalid_job_qs,
    normalized_job_number,
    suggest_replacement_jobs,
    valid_replacement_jobs,
)

from .base import AppTestCase


class JobCleanupNormalizationTests(AppTestCase):
    def test_normalized_job_number_removes_punctuation_spaces_and_case(self):
        self.assertEqual(normalized_job_number(" 26-001 / a "), "26001A")

    def test_normalized_job_number_handles_blank_values(self):
        self.assertEqual(normalized_job_number(None), "")
        self.assertEqual(normalized_job_number(""), "")


class InvalidJobQueryTests(AppTestCase):
    def test_invalid_job_qs_only_returns_blank_description_jobs_sorted(self):
        self.make_job_record(job_number="BAD-20", description="")
        self.make_job_record(job_number="BAD-10", description="")
        self.make_job_record(job_number="GOOD-1", description="Valid job")

        self.assertEqual(
            list(invalid_job_qs().values_list("job_number", flat=True)),
            ["BAD-10", "BAD-20"],
        )

    def test_valid_replacement_jobs_only_returns_active_described_jobs_sorted(self):
        self.make_job_record(job_number="26020", active=True, description="Valid B")
        self.make_job_record(job_number="26010", active=True, description="Valid A")
        self.make_job_record(job_number="26030", active=False, description="Inactive")
        self.make_job_record(job_number="26040", active=True, description="")

        self.assertEqual(
            list(valid_replacement_jobs().values_list("job_number", flat=True)),
            ["26010", "26020"],
        )


class InvalidJobEntryTests(AppTestCase):
    def setUp(self):
        self.user = self.make_user(username="cleanup_user")
        self.timesheet = self.make_timesheet_record(
            employee=self.user,
            week_start=date(2026, 8, 2),
        )
        self.invalid_job = self.make_job_record(job_number="BAD-001", description="")

    def test_entries_for_invalid_job_matches_linked_and_free_text_case_insensitively(self):
        linked = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=1,
            job=self.invalid_job,
            job_number="",
        )
        free_text = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=2,
            job=None,
            job_number="bad-001",
        )
        other = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=3,
            job=None,
            job_number="OTHER",
        )

        result_ids = set(entries_for_invalid_job(self.invalid_job).values_list("id", flat=True))

        self.assertEqual(result_ids, {linked.id, free_text.id})
        self.assertNotIn(other.id, result_ids)


class SuggestReplacementJobTests(AppTestCase):
    def test_blank_invalid_job_number_returns_no_suggestions(self):
        self.make_job_record(job_number="26001")
        self.assertEqual(suggest_replacement_jobs("   "), [])

    def test_suggestions_ignore_invalid_replacement_candidates(self):
        valid = self.make_job_record(job_number="26001", description="Valid")
        self.make_job_record(job_number="26002", description="")
        self.make_job_record(job_number="26003", active=False, description="Inactive")

        suggestions = suggest_replacement_jobs("2600")
        suggested_ids = [job.id for _, job in suggestions]

        self.assertEqual(suggested_ids, [valid.id])

    def test_suggestions_rank_exact_prefix_and_fuzzy_matches(self):
        exact = self.make_job_record(job_number="26-001", description="Exact")
        prefix = self.make_job_record(job_number="260012", description="Prefix")
        shorter = self.make_job_record(job_number="2600", description="Shorter")
        fuzzy = self.make_job_record(job_number="26091", description="Fuzzy")
        self.make_job_record(job_number="99999", description="Unrelated")

        suggestions = suggest_replacement_jobs("26 001", limit=10)

        self.assertEqual(suggestions[0], (100, exact))
        self.assertEqual(suggestions[1], (100, prefix))
        self.assertEqual(suggestions[2], (95, shorter))
        self.assertIn(fuzzy, [job for _, job in suggestions])
        self.assertNotIn("99999", [job.job_number for _, job in suggestions])

    def test_suggestions_are_sorted_by_job_number_when_scores_tie(self):
        first = self.make_job_record(job_number="ABC1234", description="First")
        second = self.make_job_record(job_number="ABC1235", description="Second")

        suggestions = suggest_replacement_jobs("ABC123", limit=5)

        self.assertEqual([job for _, job in suggestions], [first, second])

    def test_suggestion_limit_is_applied(self):
        for suffix in range(10):
            self.make_job_record(job_number=f"2600{suffix}", description=f"Job {suffix}")

        self.assertEqual(len(suggest_replacement_jobs("2600", limit=3)), 3)


class CleanupInvalidJobTests(AppTestCase):
    def setUp(self):
        self.user = self.make_user(username="cleanup_action_user")
        self.timesheet = self.make_timesheet_record(
            employee=self.user,
            week_start=date(2026, 8, 2),
        )
        self.invalid_job = self.make_job_record(job_number="BAD-100", description="")

    def test_cleanup_without_replacement_clears_entries_and_deletes_invalid_job(self):
        linked = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=1,
            job=self.invalid_job,
            job_number="BAD-100",
        )
        free_text = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=2,
            job_number="bad-100",
        )
        untouched = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=3,
            job_number="26001",
        )

        count = cleanup_invalid_job(self.invalid_job)

        self.assertEqual(count, 2)
        self.assertFalse(Job.objects.filter(pk=self.invalid_job.pk).exists())

        linked.refresh_from_db()
        free_text.refresh_from_db()
        untouched.refresh_from_db()

        self.assertIsNone(linked.job)
        self.assertEqual(linked.job_number, "")
        self.assertIsNone(free_text.job)
        self.assertEqual(free_text.job_number, "")
        self.assertEqual(untouched.job_number, "26001")

    def test_cleanup_with_replacement_reassigns_entries_and_deletes_invalid_job(self):
        replacement = self.make_job_record(job_number="26055", description="Replacement")
        linked = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=1,
            job=self.invalid_job,
            job_number="BAD-100",
        )
        free_text = self.make_time_entry_record(
            timesheet=self.timesheet,
            row_order=2,
            job_number="bad-100",
        )

        count = cleanup_invalid_job(self.invalid_job, replacement)

        self.assertEqual(count, 2)
        self.assertFalse(Job.objects.filter(pk=self.invalid_job.pk).exists())

        for entry in (linked, free_text):
            entry.refresh_from_db()
            self.assertEqual(entry.job, replacement)
            self.assertEqual(entry.job_number, replacement.job_number)

    def test_cleanup_with_no_matching_entries_still_deletes_invalid_job(self):
        count = cleanup_invalid_job(self.invalid_job)

        self.assertEqual(count, 0)
        self.assertFalse(Job.objects.filter(pk=self.invalid_job.pk).exists())
