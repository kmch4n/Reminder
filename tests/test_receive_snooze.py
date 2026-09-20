import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from linebot.v3.messaging.exceptions import ApiException

os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "dummy-token")
os.environ.setdefault("LINE_CHANNEL_SECRET", "dummy-secret")

import receive
from reminder.session import clear_user_session


def build_text_event(
    webhook_event_id: str,
    *,
    timestamp: int = 1_800_000_000_000,
    is_redelivery: bool = False,
) -> receive.MessageEvent:
    """Build a complete LINE text event for webhook behavior tests."""
    return receive.MessageEvent.from_dict(
        {
            "type": "message",
            "source": {"type": "user", "userId": "test-user"},
            "timestamp": timestamp,
            "mode": "active",
            "webhookEventId": webhook_event_id,
            "deliveryContext": {"isRedelivery": is_redelivery},
            "replyToken": "test-reply-token",
            "message": {
                "id": "test-message-id",
                "type": "text",
                "quoteToken": "test-quote-token",
                "text": "リマインド一覧",
            },
        }
    )


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


class WebhookRedeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_user_session("test-user")

    def tearDown(self) -> None:
        clear_user_session("test-user")

    def test_duplicate_webhook_event_is_processed_only_once(self) -> None:
        event = build_text_event("duplicate-event")

        with patch.object(
            receive,
            "create_reminder_list_flex",
            return_value=None,
        ), patch.object(receive.MessagingApi, "reply_message") as reply_message:
            receive.handle_text_message(event)
            receive.handle_text_message(event)

        self.assertEqual(reply_message.call_count, 1)

    def test_stale_redelivery_is_ignored(self) -> None:
        event = build_text_event(
            "stale-redelivery",
            timestamp=1,
            is_redelivery=True,
        )

        with patch.object(
            receive,
            "create_reminder_list_flex",
            return_value=None,
        ), patch.object(receive.MessagingApi, "reply_message") as reply_message:
            receive.handle_text_message(event)

        reply_message.assert_not_called()

    def test_invalid_reply_token_does_not_trigger_webhook_redelivery(self) -> None:
        class InvalidReplyTokenResponse:
            status = 400
            reason = "Bad Request"
            data = '{"message":"Invalid reply token"}'

            @staticmethod
            def getheaders() -> dict[str, str]:
                return {}

        error = ApiException(http_resp=InvalidReplyTokenResponse())

        with receive.app.test_client() as cl, patch.object(
            receive.handler,
            "handle",
            side_effect=error,
        ):
            response = cl.post(
                "/reminder/callback",
                data="{}",
                headers={"X-Line-Signature": "test-signature"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "OK")


if __name__ == "__main__":
    unittest.main()
