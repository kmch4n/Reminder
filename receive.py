#!/usr/bin/env python3
"""
receive.py - Flask webhook server for LINE bot

Interactive reminder registration system with natural language time parsing.
"""

import os
import sys
import json
import uuid
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Make sure environment variables are set.")

# Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
DATA_DIR = os.getenv('REMINDKUN_DATA_DIR', './data')
TIMEZONE = os.getenv('REMINDKUN_TIMEZONE', 'Asia/Tokyo')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set")
    sys.exit(1)

# Initialize Flask app
app = Flask(__name__)

# Initialize LINE bot SDK
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Timezone object
TZ = ZoneInfo(TIMEZONE)

# Session storage (in-memory, lost on restart)
# Structure: {user_id: {"state": "waiting_for_time", "message": "text", "fail_count": 0}}
user_sessions: Dict[str, Dict[str, Any]] = {}

# Maximum number of failed attempts before clearing session
MAX_FAIL_COUNT = 5


# ============================================================================
# JSON Storage Functions
# ============================================================================

def get_reminders_file_path() -> Path:
    """Get the path to the reminders JSON file."""
    return Path(DATA_DIR) / 'reminders.json'


def load_reminders_from_file() -> List[Dict[str, Any]]:
    """Load all reminders from JSON file."""
    file_path = get_reminders_file_path()

    if not file_path.exists():
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        app.logger.error(f"Error loading reminders: {e}")
        return []


def save_reminders_to_file(reminders: List[Dict[str, Any]]) -> None:
    """Save all reminders to JSON file."""
    file_path = get_reminders_file_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except IOError as e:
        app.logger.error(f"Error saving reminders: {e}")
        raise


def add_reminder_to_file(reminder: Dict[str, Any]) -> None:
    """Add a new reminder to the JSON file."""
    reminders = load_reminders_from_file()
    reminders.append(reminder)
    save_reminders_to_file(reminders)


# ============================================================================
# Time Utility Functions
# ============================================================================

def get_current_time() -> datetime:
    """Get current time in configured timezone."""
    return datetime.now(TZ)


def get_weekday_number(weekday_text: str) -> Optional[int]:
    """
    Convert Japanese or English weekday text to weekday number (0=Monday, 6=Sunday).

    Args:
        weekday_text: Weekday in Japanese or English

    Returns:
        Weekday number (0-6) or None if not recognized.
    """
    weekday_map = {
        '月曜': 0, '月': 0, '月曜日': 0,
        '火曜': 1, '火': 1, '火曜日': 1,
        '水曜': 2, '水': 2, '水曜日': 2,
        '木曜': 3, '木': 3, '木曜日': 3,
        '金曜': 4, '金': 4, '金曜日': 4,
        '土曜': 5, '土': 5, '土曜日': 5,
        '日曜': 6, '日': 6, '日曜日': 6,
    }
    return weekday_map.get(weekday_text)


# ============================================================================
# Natural Language Time Parsing
# ============================================================================

def parse_natural_time(text: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Parse natural language time expressions.

    Supported formats:
    - 22:00, 14時, 午後3時, 午前9時30分
    - 今日の22:00, 今日23:59
    - 明日の9:00, 明日午後3時
    - 明後日の午前9時
    - 10分後, 2時間後, 3日後
    - 来週火曜日の21時
    - 毎週日曜日 20時
    - 毎月1日 20時
    - 2025-11-20, 11/20 (defaults to 9:00)

    Args:
        text: Natural language time expression

    Returns:
        Tuple of (schedule dict, formatted description) or None if parsing fails.
    """
    text = text.strip()
    now = get_current_time()

    # Helper function to parse time with 午前/午後
    def parse_time_with_ampm(time_text: str) -> Tuple[int, int]:
        """Parse time text with 午前/午後. Returns (hour, minute)."""
        # 午後3時30分, 午前9時
        match = re.match(r'午後\s*(\d{1,2})時?(\d{0,2})分?', time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            if hour != 12:
                hour += 12
            return (hour, minute)

        match = re.match(r'午前\s*(\d{1,2})時?(\d{0,2})分?', time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            if hour == 12:
                hour = 0
            return (hour, minute)

        # Regular HH:MM or HH時MM分
        match = re.match(r'(\d{1,2})[時:](\d{0,2})分?', time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            return (hour, minute)

        return None

    # Pattern 0a: N分後 (relative minutes)
    match = re.match(r'(\d+)分後', text)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0 or minutes > 1440:  # Max 24 hours
            return None

        target_time = now + timedelta(minutes=minutes)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 0b: N時間後 (relative hours)
    match = re.match(r'(\d+)時間後', text)
    if match:
        hours = int(match.group(1))
        if hours <= 0 or hours > 168:  # Max 7 days
            return None

        target_time = now + timedelta(hours=hours)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 0c: N日後 HH:MM (relative days with time)
    match = re.match(r'(\d+)日後\s+(.+)', text)
    if match:
        days = int(match.group(1))
        time_part = match.group(2)

        if days <= 0 or days > 365:
            return None

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple
        target_time = now + timedelta(days=days)
        target_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 0d: N日後 (relative days, default 9:00)
    match = re.match(r'(\d+)日後$', text)
    if match:
        days = int(match.group(1))

        if days <= 0 or days > 365:
            return None

        target_time = now + timedelta(days=days)
        target_time = target_time.replace(hour=9, minute=0, second=0, microsecond=0)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 09:00")
        return (schedule, desc)

    # Pattern 1: 毎週 曜日 時刻 (recurring weekly)
    match = re.match(r'毎週\s*([月火水木金土日]曜?日?)\s*(.+)', text)
    if match:
        weekday_text = match.group(1)
        time_part = match.group(2)

        weekday = get_weekday_number(weekday_text)
        if weekday is None:
            return None

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple
        time_str = f"{hour:02d}:{minute:02d}"

        schedule = {
            "type": "weekly",
            "weekday": weekday,
            "time": time_str
        }
        desc = f"毎週{weekday_text} {time_str}"
        return (schedule, desc)

    # Pattern 2: 毎月 DD日 時刻 (recurring monthly)
    match = re.match(r'毎月\s*(\d{1,2})日?\s*(.+)', text)
    if match:
        day = int(match.group(1))
        time_part = match.group(2)

        if not 1 <= day <= 31:
            return None

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple
        time_str = f"{hour:02d}:{minute:02d}"

        schedule = {
            "type": "monthly",
            "day": day,
            "time": time_str
        }
        desc = f"毎月{day}日 {time_str}"
        return (schedule, desc)

    # Pattern 3: 来週○曜日 時刻
    match = re.match(r'来週\s*([月火水木金土日]曜?日?)\s*(.+)', text)
    if match:
        weekday_text = match.group(1)
        time_part = match.group(2)

        weekday = get_weekday_number(weekday_text)
        if weekday is None:
            return None

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        # Calculate next week's target weekday
        days_ahead = weekday - now.weekday() + 7  # Always next week

        target_time = now + timedelta(days=days_ahead)
        target_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日(%a) %H:%M").replace('Mon', '月').replace('Tue', '火').replace('Wed', '水').replace('Thu', '木').replace('Fri', '金').replace('Sat', '土').replace('Sun', '日')
        return (schedule, desc)

    # Pattern 4: 明後日 時刻
    match = re.match(r'明後日\s*(.+)', text)
    if match:
        time_part = match.group(1).replace('の', '').strip()

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        target_time = now + timedelta(days=2)
        target_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 5: 明日 時刻
    match = re.match(r'明日\s*(.+)', text)
    if match:
        time_part = match.group(1).replace('の', '').strip()

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        target_time = now + timedelta(days=1)
        target_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 6: 今日 時刻
    match = re.match(r'今日\s*(.+)', text)
    if match:
        time_part = match.group(1).replace('の', '').strip()

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If time has passed today, move to tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 7: 時刻のみ (HH:MM, HH時, 午後3時など) → 今日のその時刻
    time_tuple = parse_time_with_ampm(text)
    if time_tuple is not None:
        hour, minute = time_tuple

        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If time has passed today, move to tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)

        schedule = {
            "type": "once",
            "run_at": target_time.isoformat()
        }
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 8: 日付のみ YYYY-MM-DD → デフォルト9:00
    match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})$', text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))

        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
            schedule = {
                "type": "once",
                "run_at": target_time.isoformat()
            }
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 9: 日付のみ MM/DD → デフォルト9:00
    match = re.match(r'(\d{1,2})/(\d{1,2})$', text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year

        # If the date has passed this year, use next year
        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
            if target_time <= now:
                target_time = datetime(year + 1, month, day, 9, 0, tzinfo=TZ)

            schedule = {
                "type": "once",
                "run_at": target_time.isoformat()
            }
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 10: 日付のみ M月D日 → デフォルト9:00
    match = re.match(r'(\d{1,2})月(\d{1,2})日?$', text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year

        # If the date has passed this year, use next year
        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
            if target_time <= now:
                target_time = datetime(year + 1, month, day, 9, 0, tzinfo=TZ)

            schedule = {
                "type": "once",
                "run_at": target_time.isoformat()
            }
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 11: YYYY年M月D日 (20XX年5月3日) → デフォルト9:00
    match = re.match(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?$', text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))

        # Block dates more than 5 years in the future
        max_year = now.year + 5
        if year > max_year:
            return None

        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)

            # Check if time is in the past
            if is_past_time(target_time):
                return None

            schedule = {
                "type": "once",
                "run_at": target_time.isoformat()
            }
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 12: YYYY年M月D日 時刻付き (2025年5月3日 14:00)
    match = re.match(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?\s+(.+)', text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        time_part = match.group(4)

        # Block dates more than 5 years in the future
        max_year = now.year + 5
        if year > max_year:
            return None

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        try:
            target_time = datetime(year, month, day, hour, minute, tzinfo=TZ)

            # Check if time is in the past
            if is_past_time(target_time):
                return None

            schedule = {
                "type": "once",
                "run_at": target_time.isoformat()
            }
            desc = target_time.strftime("%Y年%m月%d日 %H:%M")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 13: YYYY-MM-DD HH:MM (structured format with time)
    match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))

        # Block dates more than 5 years in the future
        max_year = now.year + 5
        if year > max_year:
            return None

        try:
            target_time = datetime(year, month, day, hour, minute, tzinfo=TZ)

            # Check if time is in the past
            if is_past_time(target_time):
                return None

            schedule = {
                "type": "once",
                "run_at": target_time.isoformat()
            }
            desc = target_time.strftime("%Y年%m月%d日 %H:%M")
            return (schedule, desc)
        except ValueError:
            return None

    return None


def is_past_time(target_time: datetime) -> bool:
    """
    Check if the target time is in the past.

    Args:
        target_time: Target datetime to check

    Returns:
        True if target time is in the past, False otherwise.
    """
    now = get_current_time()
    return target_time < now


def create_time_quick_reply() -> QuickReply:
    """
    Create quick reply buttons for time selection.

    Returns:
        QuickReply object with time selection options.
    """
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="10分後", text="10分後")),
        QuickReplyItem(action=MessageAction(label="30分後", text="30分後")),
        QuickReplyItem(action=MessageAction(label="1時間後", text="1時間後")),
        QuickReplyItem(action=MessageAction(label="明日9時", text="明日 9時")),
        QuickReplyItem(action=MessageAction(label="明日20時", text="明日 20時")),
        QuickReplyItem(action=MessageAction(label="毎週月曜20時", text="毎週月曜 20時")),
        QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル"))
    ])


def calculate_initial_run_at(schedule: Dict[str, Any]) -> Optional[str]:
    """
    Calculate the first run time for a reminder based on its schedule.

    Args:
        schedule: Schedule dictionary

    Returns:
        ISO 8601 datetime string or None if calculation fails.
    """
    schedule_type = schedule.get("type")

    if schedule_type == "once":
        return schedule.get("run_at")

    elif schedule_type == "weekly":
        weekday = schedule.get("weekday")
        time_str = schedule.get("time")

        if weekday is None or time_str is None:
            return None

        now = get_current_time()
        target_time = datetime.strptime(time_str, "%H:%M").time()

        days_ahead = weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            if now.time() >= target_time:
                days_ahead = 7

        next_run = now + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=target_time.hour, minute=target_time.minute,
                                     second=0, microsecond=0)

        return next_run.isoformat()

    elif schedule_type == "monthly":
        day = schedule.get("day")
        time_str = schedule.get("time")

        if day is None or time_str is None:
            return None

        now = get_current_time()
        target_time = datetime.strptime(time_str, "%H:%M").time()

        try:
            next_run = now.replace(day=day, hour=target_time.hour,
                                   minute=target_time.minute, second=0, microsecond=0)

            if next_run <= now:
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
        except ValueError:
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=day,
                                       hour=target_time.hour, minute=target_time.minute,
                                       second=0, microsecond=0)
            else:
                next_run = now.replace(month=now.month + 1, day=day,
                                       hour=target_time.hour, minute=target_time.minute,
                                       second=0, microsecond=0)

        return next_run.isoformat()

    return None


# ============================================================================
# Reminder Creation
# ============================================================================

def create_reminder_object(user_id: str, message: str, schedule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a complete reminder object.

    Args:
        user_id: LINE user ID
        message: Reminder message text
        schedule: Schedule dictionary

    Returns:
        Complete reminder object.
    """
    next_run_at = calculate_initial_run_at(schedule)
    created_at = get_current_time().isoformat()

    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "text": message,
        "schedule": schedule,
        "next_run_at": next_run_at,
        "created_at": created_at,
        "status": "pending"
    }


# ============================================================================
# Session Management
# ============================================================================

def start_waiting_for_time_session(user_id: str, message: str) -> None:
    """Start a session waiting for time input."""
    user_sessions[user_id] = {
        "state": "waiting_for_time",
        "message": message,
        "fail_count": 0
    }


def increment_fail_count(user_id: str) -> int:
    """Increment and return the fail count for a user session."""
    if user_id in user_sessions:
        user_sessions[user_id]["fail_count"] = user_sessions[user_id].get("fail_count", 0) + 1
        return user_sessions[user_id]["fail_count"]
    return 0


def get_user_session(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's current session."""
    return user_sessions.get(user_id)


def clear_user_session(user_id: str) -> None:
    """Clear user's session."""
    if user_id in user_sessions:
        del user_sessions[user_id]


# ============================================================================
# LINE Webhook Handler
# ============================================================================

@app.route("/reminder/callback", methods=['POST'])
def callback():
    """LINE webhook callback endpoint."""
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        abort(400)

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature")
        abort(400)

    return 'OK'


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

        reply_text = f"「{received_text}」ですね。\n次に、いつ送信してほしいかを送信して下さい。"
        quick_reply = create_time_quick_reply()

    # Send reply message
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text, quick_reply=quick_reply)]
            )
        )


@app.route("/reminder/health", methods=['GET'])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Reminder bot webhook server is running"}


if __name__ == "__main__":
    # Suppress Flask's default request logging
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)

    print("Starting Reminder Bot webhook server...")
    print(f"Public URL: https://linebot.kmchan.jp/reminder/callback")
    print(f"Data: {DATA_DIR} | TZ: {TIMEZONE}")
    app.run(host="0.0.0.0", port=8000, debug=False)
