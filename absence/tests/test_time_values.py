"""Regression tests for absence/time values."""

from datetime import date

from django.test import SimpleTestCase

from absence.services.time_values import count_workdays, format_hhmm, is_full_employment_week_range, parse_hhmm


class TimeValueTests(SimpleTestCase):
    """Exercise the time value workflow and protect its expected behavior from regressions."""
    def test_signed_hhmm_round_trip(self):
        """Verify that signed hhmm round trip."""
        for source, minutes in [("73:01", 4381), ("-26:16", -1576), ("0:00", 0), ("126:45", 7605)]:
            self.assertEqual(parse_hhmm(source), minutes)
            self.assertEqual(format_hhmm(minutes), source)

    def test_rejects_invalid_minutes(self):
        """Verify that rejects invalid minutes."""
        with self.assertRaises(ValueError):
            parse_hhmm("10:60")

    def test_counts_only_weekdays(self):
        """Verify that counts only weekdays."""
        self.assertEqual(count_workdays(date(2026, 9, 7), date(2026, 9, 13)), 5)

    def test_full_employment_week_range_requires_monday_through_friday_blocks(self):
        """Verify that full employment week range requires monday through friday blocks."""
        self.assertTrue(is_full_employment_week_range(date(2026, 9, 7), date(2026, 9, 11)))
        self.assertTrue(is_full_employment_week_range(date(2026, 9, 7), date(2026, 9, 18)))
        self.assertFalse(is_full_employment_week_range(date(2026, 9, 8), date(2026, 9, 11)))
