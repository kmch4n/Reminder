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
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# Import local modules
from storage import add_reminder_to_file
from time_parser import parse_natural_time, create_time_quick_reply
from session import (
    get_user_session,
    clear_user_session,
    start_waiting_for_time_session,
    increment_fail_count,
    MAX_FAIL_COUNT,
)
from helpers import create_reminder_object, format_reminder_list

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
DATA_DIR = os.getenv("REMINDKUN_DATA_DIR", "./data")
TIMEZONE = os.getenv("REMINDKUN_TIMEZONE", "Asia/Tokyo")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set")
    sys.exit(1)

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
        reply_text = format_reminder_list(user_id)

        # Send reply message
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)],
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
                        f"✅ リマインダーを追加しました。\n\n"
                        f"時刻: {time_desc}\n"
                        f"内容: 「{reminder_message}」"
                    )
                except Exception as e:
                    app.logger.error(f"Error saving reminder: {e}")
                    reply_text = "❌ リマインダーの登録に失敗しました"

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

    else:
        # User is sending a new reminder message
        # Start a new session and ask for time

        start_waiting_for_time_session(user_id, received_text)

        reply_text = (
            f"「{received_text}」ですね。\n次に、いつ送信してほしいかを送信して下さい。"
        )
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
    print(f"Public URL: https://linebot.kmchan.jp/reminder/callback")
    print(f"Data: {DATA_DIR} | TZ: {TIMEZONE}")
    app.run(host="0.0.0.0", port=8000, debug=False)
