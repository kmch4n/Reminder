import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from reminder import time_parser


class ParseNaturalTimeRelativeDayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixed_now = datetime(2026, 4, 4, 8, 30, tzinfo=ZoneInfo("Asia/Tokyo"))

    def parse(self, text: str):
        with patch.object(time_parser, "get_current_time", return_value=self.fixed_now):
            return time_parser.parse_natural_time(text)

    def test_numeric_relative_day_uses_default_time(self) -> None:
        result = self.parse("1日後")

        self.assertIsNotNone(result)
        schedule, desc = result
        self.assertEqual(schedule["type"], "once")
        self.assertEqual(schedule["run_at"], "2026-04-05T09:00:00+09:00")
        self.assertEqual(desc, "2026年04月05日 09:00")

    def test_kanji_relative_day_matches_numeric_behavior(self) -> None:
        numeric_result = self.parse("1日後")
        kanji_result = self.parse("一日後")

        self.assertEqual(kanji_result, numeric_result)

    def test_kanji_relative_day_with_time_without_space(self) -> None:
        result = self.parse("一日後14時")

        self.assertIsNotNone(result)
        schedule, desc = result
        self.assertEqual(schedule["run_at"], "2026-04-05T14:00:00+09:00")
        self.assertEqual(desc, "2026年04月05日 14:00")

    def test_large_kanji_relative_day_is_supported(self) -> None:
        result = self.parse("三百六十五日後")

        self.assertIsNotNone(result)
        schedule, desc = result
        self.assertEqual(schedule["run_at"], "2027-04-04T09:00:00+09:00")
        self.assertEqual(desc, "2027年04月04日 09:00")

    def test_zero_day_inputs_are_rejected(self) -> None:
        self.assertIsNone(self.parse("0日後"))
        self.assertIsNone(self.parse("零日後"))

    def test_day_count_over_limit_is_rejected(self) -> None:
        self.assertIsNone(self.parse("366日後"))


class ParseNaturalTimeMonthlyTests(unittest.TestCase):
    def setUp(self) -> None:
        # 08:30 JST — DEFAULT_TIME(09:00) より前なので明示時刻と区別しやすい
        self.fixed_now = datetime(2026, 4, 4, 8, 30, tzinfo=ZoneInfo("Asia/Tokyo"))

    def parse(self, text: str):
        with patch.object(time_parser, "get_current_time", return_value=self.fixed_now):
            return time_parser.parse_natural_time(text)

    def test_monthly_no_time_uses_default_time(self) -> None:
        result = self.parse("毎月20日")
        self.assertIsNotNone(result)
        schedule, desc = result
        self.assertEqual(schedule["type"], "monthly")
        self.assertEqual(schedule["day"], 20)
        self.assertEqual(schedule["time"], "09:00")
        self.assertIn("毎月20日", desc)
        self.assertIn("09:00", desc)

    def test_monthly_no_kanji_nichi_uses_default_time(self) -> None:
        result = self.parse("毎月20")
        self.assertIsNotNone(result)
        schedule, _ = result
        self.assertEqual(schedule["day"], 20)
        self.assertEqual(schedule["time"], "09:00")

    def test_monthly_with_explicit_time(self) -> None:
        result = self.parse("毎月20日 21時")
        self.assertIsNotNone(result)
        schedule, desc = result
        self.assertEqual(schedule["type"], "monthly")
        self.assertEqual(schedule["day"], 20)
        self.assertEqual(schedule["time"], "21:00")
        self.assertEqual(desc, "毎月20日 21:00")

    def test_monthly_with_explicit_time_no_space(self) -> None:
        result = self.parse("毎月20日21時")
        self.assertIsNotNone(result)
        schedule, _ = result
        self.assertEqual(schedule["time"], "21:00")

    def test_monthly_with_ampm_time(self) -> None:
        result = self.parse("毎月20日 午後9時30分")
        self.assertIsNotNone(result)
        schedule, _ = result
        self.assertEqual(schedule["time"], "21:30")

    def test_monthly_day_31_uses_default_time(self) -> None:
        result = self.parse("毎月31日")
        self.assertIsNotNone(result)
        schedule, _ = result
        self.assertEqual(schedule["day"], 31)
        self.assertEqual(schedule["time"], "09:00")

    def test_monthly_day_32_is_rejected(self) -> None:
        self.assertIsNone(self.parse("毎月32日"))

    def test_monthly_day_0_is_rejected(self) -> None:
        self.assertIsNone(self.parse("毎月0日"))

    def test_monthly_invalid_time_text_is_rejected(self) -> None:
        self.assertIsNone(self.parse("毎月20日 今日"))

    def test_monthly_with_leading_space_in_day(self) -> None:
        result = self.parse("毎月 5日")
        self.assertIsNotNone(result)
        schedule, _ = result
        self.assertEqual(schedule["day"], 5)


if __name__ == "__main__":
    unittest.main()
