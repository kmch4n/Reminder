import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "dummy-token")
os.environ.setdefault("LINE_CHANNEL_SECRET", "dummy-secret")

import receive


class HandleSnoozeRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quick_reply = object()
        self.now = datetime(2026, 4, 4, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    def test_allows_snooze_for_old_notification(self) -> None:
        last_notification = {
            "reminder_id": "reminder-1",
            "text": "Take out trash",
            "sent_at": "2026-04-01T09:00:00+09:00",
        }

        with patch.object(
            receive,
            "create_main_menu_quick_reply",
            return_value=self.quick_reply,
        ), patch.object(
            receive,
            "get_last_notification",
            return_value=last_notification,
        ), patch.object(
            receive,
            "get_current_time",
            return_value=self.now,
        ), patch.object(
            receive,
            "create_reminder_object",
            return_value={"id": "snooze-1", "text": "Take out trash"},
        ) as create_reminder_object, patch.object(
            receive,
            "add_reminder_to_file",
        ) as add_reminder_to_file, patch.object(
            receive,
            "set_last_notification",
        ) as set_last_notification:
            reply_text, quick_reply = receive.handle_snooze_request(
                "user-1", timedelta(minutes=10)
            )

        self.assertEqual(
            reply_text,
            "⏰ 「Take out trash」を2026年04月04日 12:10に再通知します。",
        )
        self.assertIs(quick_reply, self.quick_reply)
        create_reminder_object.assert_called_once_with(
            "user-1",
            "Take out trash",
            {"type": "once", "run_at": "2026-04-04T12:10:00+09:00"},
            extra_fields={"is_snooze": True, "snoozed_from": "reminder-1"},
        )
        add_reminder_to_file.assert_called_once_with(
            {"id": "snooze-1", "text": "Take out trash"}
        )
        set_last_notification.assert_called_once_with(
            "user-1",
            {
                "reminder_id": "reminder-1",
                "text": "Take out trash",
                "sent_at": "2026-04-01T09:00:00+09:00",
                "pending_snooze_id": "snooze-1",
                "pending_snooze_run_at": "2026-04-04T12:10:00+09:00",
            },
        )

    def test_returns_missing_message_when_history_does_not_exist(self) -> None:
        with patch.object(
            receive,
            "create_main_menu_quick_reply",
            return_value=self.quick_reply,
        ), patch.object(
            receive,
            "get_last_notification",
            return_value=None,
        ):
            reply_text, quick_reply = receive.handle_snooze_request(
                "user-1", timedelta(minutes=10)
            )

        self.assertEqual(reply_text, "直近のリマインダーが見つかりませんでした。")
        self.assertIs(quick_reply, self.quick_reply)


if __name__ == "__main__":
    unittest.main()
