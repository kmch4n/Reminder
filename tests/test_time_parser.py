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


if __name__ == "__main__":
    unittest.main()
