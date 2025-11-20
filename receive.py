#!/usr/bin/env python3
"""
receive.py - Flask webhook server for LINE bot

Interactive reminder registration system with natural language time parsing.
"""

import os
import sys

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# Import local modules
from storage import add_reminder_to_file
from time_parser import (
    parse_natural_time,
    create_time_quick_reply,
    create_main_menu_quick_reply,
    create_delete_quick_reply,
)
from session import (
    get_user_session,
    clear_user_session,
    start_waiting_for_time_session,
    start_waiting_for_delete_id_session,
    start_waiting_for_delete_all_confirmation_session,
    increment_fail_count,
    MAX_FAIL_COUNT,
)
from helpers import (
    create_reminder_object,
    format_reminder_list,
    create_reminder_list_flex,
    format_reminder_list_for_deletion,
    create_reminder_deletion_flex,
    delete_reminder_by_id,
    delete_all_reminders,
)

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "Warning: python-dotenv not installed. Make sure environment variables are set."
    )

# Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
DATA_DIR = os.getenv("REMINDER_DATA_DIR", "./data")
TIMEZONE = os.getenv("REMINDER_TIMEZONE", "Asia/Tokyo")
PUBLIC_URL = os.getenv(
    "REMINDER_PUBLIC_URL", "https://your-domain.com/reminder/callback"
)

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set")
    sys.exit(1)


def load_settings():
    """
    Load settings from data/settings.json.

    Returns:
        dict: Settings dictionary with default values if file doesn't exist.
    """
    import json

    settings_file = os.path.join(DATA_DIR, "settings.json")

    # Default settings
    default_settings = {"use_flex_message": True}

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Merge with defaults to ensure all keys exist
            return {**default_settings, **settings}
    except FileNotFoundError:
        return default_settings
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON in {settings_file}, using defaults")
        return default_settings


# Initialize Flask app
app = Flask(__name__)

# Initialize LINE bot SDK
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


# ============================================================================
# LINE Webhook Handler
# ============================================================================


@app.route("/reminder/callback", methods=["POST"])
def callback():
    """LINE webhook callback endpoint."""
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        abort(400)

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature")
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    """
    Handle text message events with interactive flow.

    Flow:
    1. User sends reminder message → Bot asks for time
    2. User sends time → Bot creates reminder
    """
    received_text = event.message.text.strip()
    user_id = event.source.user_id

    # Check for reminder list command
    if received_text == "リマインド一覧":
        settings = load_settings()
        use_flex = settings.get("use_flex_message", True)
        quick_reply = create_main_menu_quick_reply()

        # Send reply message
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            if use_flex:
                # Use Flex Message
                flex_contents = create_reminder_list_flex(user_id)

                if flex_contents:
                    # Send Flex Message
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                FlexMessage(
                                    alt_text="リマインダー一覧",
                                    contents=FlexContainer.from_dict(flex_contents),
                                    quick_reply=quick_reply,
                                )
                            ],
                        )
                    )
                else:
                    # No reminders - send text message
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                TextMessage(
                                    text="📋 登録されているリマインダーはありません。",
                                    quick_reply=quick_reply,
                                )
                            ],
                        )
                    )
            else:
                # Use text message
                reminder_text = format_reminder_list(user_id)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(
                                text=reminder_text,
                                quick_reply=quick_reply,
                            )
                        ],
                    )
                )
        return

    # Check for reminder delete command
    if received_text == "リマインド削除":
        settings = load_settings()
        use_flex = settings.get("use_flex_message", True)
        quick_reply = create_main_menu_quick_reply()

        # Send reply message
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            if use_flex:
                # Use Flex Message
                result = create_reminder_deletion_flex(user_id)

                if result:
                    flex_contents, reminders = result
                    # Start delete session
                    start_waiting_for_delete_id_session(user_id, reminders)
                    quick_reply = create_delete_quick_reply(len(reminders))

                    # Send Flex Message
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                FlexMessage(
                                    alt_text="リマインダー削除",
                                    contents=FlexContainer.from_dict(flex_contents),
                                    quick_reply=quick_reply,
                                )
                            ],
                        )
                    )
                else:
                    # No reminders - send text message
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                TextMessage(
                                    text="📋 削除できるリマインダーはありません。",
                                    quick_reply=quick_reply,
                                )
                            ],
                        )
                    )
            else:
                # Use text message
                reply_text, reminders = format_reminder_list_for_deletion(user_id)

                if reminders:
                    # Start delete session
                    start_waiting_for_delete_id_session(user_id, reminders)
                    quick_reply = create_delete_quick_reply(len(reminders))

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text=reply_text, quick_reply=quick_reply)
                        ],
                    )
                )
        return

    # Check if user has an active session
    session = get_user_session(user_id)

    quick_reply = None  # Will be set if we need quick reply buttons

    if session and session.get("state") == "waiting_for_time":
        # Check for cancel command
        if received_text.lower() in ["キャンセル", "cancel", "やめる"]:
            clear_user_session(user_id)
            reply_text = "リマインダーの登録をキャンセルしました。"
            quick_reply = create_main_menu_quick_reply()
        else:
            # User is sending time information
            reminder_message = session.get("message")

            # Try to parse the time
            parse_result = parse_natural_time(received_text)

            if parse_result is not None:
                schedule, time_desc = parse_result

                # Create reminder
                reminder = create_reminder_object(user_id, reminder_message, schedule)

                try:
                    add_reminder_to_file(reminder)

                    reply_text = (
                        f"✅ リマインダーを登録しました。\n\n"
                        f"時刻: {time_desc}\n"
                        f"内容: 「{reminder_message}」"
                    )
                    quick_reply = create_main_menu_quick_reply()
                except Exception as e:
                    app.logger.error(f"Error saving reminder: {e}")
                    reply_text = "❌ リマインダーの登録に失敗しました。"
                    quick_reply = create_main_menu_quick_reply()

                # Clear session
                clear_user_session(user_id)
            else:
                # Failed to parse time (could be invalid format or past time)
                fail_count = increment_fail_count(user_id)

                if fail_count >= MAX_FAIL_COUNT:
                    clear_user_session(user_id)
                    reply_text = (
                        f"⚠️ {MAX_FAIL_COUNT}回失敗したため、リマインダーの登録を中止しました。\n"
                        "最初からやり直してください。"
                    )
                    quick_reply = create_main_menu_quick_reply()
                else:
                    reply_text = (
                        f"⚠️ 時刻の形式を認識できませんでした。（{fail_count}/{MAX_FAIL_COUNT}回目）\n\n"
                        "指定された時刻が既に過ぎている可能性があります。\n\n"
                        "以下の形式で送信してください:\n"
                        "• 10分後 / 2時間後\n"
                        "• 22:00 / 14時 / 午後3時\n"
                        "• 今日の22:00 / 明日午後3時\n"
                        "• 毎週日曜日 20時\n"
                        "• 2025年5月3日 / 11/20\n\n"
                        "登録をやめる場合は「キャンセル」と送信してください。"
                    )
                    quick_reply = create_time_quick_reply()

    elif session and session.get("state") == "waiting_for_delete_id":
        # Check for cancel command
        if received_text.lower() in ["キャンセル", "cancel", "やめる"]:
            clear_user_session(user_id)
            reply_text = "リマインダーの削除をキャンセルしました。"
            quick_reply = create_main_menu_quick_reply()
        # Check for "delete all" command
        elif received_text == "すべてを削除":
            # Start delete-all confirmation session
            start_waiting_for_delete_all_confirmation_session(user_id)
            reply_text = (
                "⚠️ 本当にすべてのリマインダーを削除しますか？\n\n"
                "削除する場合は「削除」と送信してください。\n"
                "キャンセルする場合は「キャンセル」と送信してください。"
            )
            quick_reply = None
        else:
            # User is sending delete ID
            reminders = session.get("reminders", [])

            # Try to parse as number
            try:
                delete_index = int(received_text) - 1

                if 0 <= delete_index < len(reminders):
                    # Delete the reminder
                    reminder_to_delete = reminders[delete_index]
                    reminder_id = reminder_to_delete.get("id")
                    reminder_text = reminder_to_delete.get("text", "")

                    if delete_reminder_by_id(reminder_id):
                        reply_text = f"✅ リマインダーを削除しました。\n\n内容: 「{reminder_text}」"
                        quick_reply = create_main_menu_quick_reply()
                    else:
                        reply_text = "❌ リマインダーの削除に失敗しました。"
                        quick_reply = create_main_menu_quick_reply()

                    # Clear session
                    clear_user_session(user_id)
                else:
                    # Invalid number
                    fail_count = increment_fail_count(user_id)

                    if fail_count >= MAX_FAIL_COUNT:
                        clear_user_session(user_id)
                        reply_text = (
                            f"⚠️ {MAX_FAIL_COUNT}回失敗したため、削除を中止しました。\n"
                            "最初からやり直してください。"
                        )
                        quick_reply = create_main_menu_quick_reply()
                    else:
                        reply_text = (
                            f"⚠️ 無効な番号です。（{fail_count}/{MAX_FAIL_COUNT}回目）\n\n"
                            f"1〜{len(reminders)}の番号を送信してください。\n"
                            "削除をやめる場合は「キャンセル」と送信してください。"
                        )
                        quick_reply = create_delete_quick_reply(len(reminders))
            except ValueError:
                # Not a number
                fail_count = increment_fail_count(user_id)

                if fail_count >= MAX_FAIL_COUNT:
                    clear_user_session(user_id)
                    reply_text = (
                        f"⚠️ {MAX_FAIL_COUNT}回失敗したため、削除を中止しました。\n"
                        "最初からやり直してください。"
                    )
                    quick_reply = create_main_menu_quick_reply()
                else:
                    reply_text = (
                        f"⚠️ 数字を送信してください。（{fail_count}/{MAX_FAIL_COUNT}回目）\n\n"
                        f"1〜{len(reminders)}の番号を送信してください。\n"
                        "削除をやめる場合は「キャンセル」と送信してください。"
                    )
                    quick_reply = create_delete_quick_reply(len(reminders))

    elif session and session.get("state") == "waiting_for_delete_all_confirmation":
        # Check for confirmation
        if received_text in ["削除", "はい", "yes"]:
            # Delete all reminders
            deleted_count = delete_all_reminders(user_id)

            if deleted_count > 0:
                reply_text = (
                    f"✅ すべてのリマインダー（{deleted_count}件）を削除しました。"
                )
            else:
                reply_text = "削除するリマインダーがありませんでした。"

            quick_reply = create_main_menu_quick_reply()
            clear_user_session(user_id)
        elif received_text.lower() in [
            "キャンセル",
            "cancel",
            "やめる",
            "いいえ",
            "no",
        ]:
            clear_user_session(user_id)
            reply_text = "すべての削除をキャンセルしました。"
            quick_reply = create_main_menu_quick_reply()
        else:
            # Invalid input
            fail_count = increment_fail_count(user_id)

            if fail_count >= MAX_FAIL_COUNT:
                clear_user_session(user_id)
                reply_text = (
                    f"⚠️ {MAX_FAIL_COUNT}回失敗したため、削除を中止しました。\n"
                    "最初からやり直してください。"
                )
                quick_reply = create_main_menu_quick_reply()
            else:
                reply_text = f"⚠️ 「削除」または「キャンセル」と送信してください。（{fail_count}/{MAX_FAIL_COUNT}回目）"
                quick_reply = None

    else:
        # Check for reminder setup command
        if received_text == "リマインド設定":
            reply_text = (
                "リマインダーの内容を入力してください。\n\n"
                "例:\n"
                "• お金の振り込み\n"
                "• エントリーシートを送る\n"
                "• 課題を提出する"
            )
            quick_reply = create_main_menu_quick_reply()
        else:
            # User is sending a new reminder message
            # Start a new session and ask for time

            start_waiting_for_time_session(user_id, received_text)

            reply_text = f"「{received_text}」\n\nいつ通知しますか？"
            quick_reply = create_time_quick_reply()

    # Send reply message
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text, quick_reply=quick_reply)],
            )
        )


@app.route("/reminder/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Reminder bot webhook server is running"}


if __name__ == "__main__":
    # Suppress Flask's default request logging
    import logging as flask_logging

    flask_log = flask_logging.getLogger("werkzeug")
    flask_log.setLevel(flask_logging.ERROR)

    print("Starting Reminder Bot webhook server...")
    print(f"Public URL: {PUBLIC_URL}")
    print(f"Data: {DATA_DIR} | TZ: {TIMEZONE}")
    app.run(host="0.0.0.0", port=8000, debug=False)
