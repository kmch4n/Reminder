"""
time_parser.py - Natural language time parsing for Japanese reminders
"""

import os
import re
import calendar
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo

from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

# Configuration
TIMEZONE = os.getenv("REMINDER_TIMEZONE", "Asia/Tokyo")

# Timezone object
TZ = ZoneInfo(TIMEZONE)

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
        "月曜": 0,
        "月": 0,
        "月曜日": 0,
        "火曜": 1,
        "火": 1,
        "火曜日": 1,
        "水曜": 2,
        "水": 2,
        "水曜日": 2,
        "木曜": 3,
        "木": 3,
        "木曜日": 3,
        "金曜": 4,
        "金": 4,
        "金曜日": 4,
        "土曜": 5,
        "土": 5,
        "土曜日": 5,
        "日曜": 6,
        "日": 6,
        "日曜日": 6,
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
    def parse_time_with_ampm(time_text: str) -> Optional[Tuple[int, int]]:
        """Parse time text with 午前/午後. Returns (hour, minute)."""

        def validate(hour: int, minute: int) -> Optional[Tuple[int, int]]:
            if not (0 <= minute < 60):
                return None
            if not (0 <= hour < 24):
                return None
            return (hour, minute)
        # 午後3時30分, 午前9時
        match = re.match(r"午後\s*(\d{1,2})時?(\d{0,2})分?", time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            if hour != 12:
                hour += 12
            return validate(hour, minute)

        match = re.match(r"午前\s*(\d{1,2})時?(\d{0,2})分?", time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            if hour == 12:
                hour = 0
            return validate(hour, minute)

        # Regular HH:MM or HH時MM分
        match = re.match(r"(\d{1,2})[時:](\d{0,2})分?", time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            return validate(hour, minute)

        return None

    # Pattern 0a: N分後 (relative minutes)
    match = re.match(r"(\d+)分後", text)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0 or minutes > 1440:  # Max 24 hours
            return None

        target_time = now + timedelta(minutes=minutes)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 0b: N時間後 (relative hours)
    match = re.match(r"(\d+)時間後", text)
    if match:
        hours = int(match.group(1))
        if hours <= 0 or hours > 168:  # Max 7 days
            return None

        target_time = now + timedelta(hours=hours)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 0c: N日後 HH:MM (relative days with time)
    match = re.match(r"(\d+)日後\s+(.+)", text)
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
        target_time = target_time.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 0d: N日後 (relative days, default 9:00)
    match = re.match(r"(\d+)日後$", text)
    if match:
        days = int(match.group(1))

        if days <= 0 or days > 365:
            return None

        target_time = now + timedelta(days=days)
        target_time = target_time.replace(hour=9, minute=0, second=0, microsecond=0)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 09:00")
        return (schedule, desc)

    # Pattern 1: 毎週 曜日 時刻 (recurring weekly)
    match = re.match(r"毎週\s*([月火水木金土日]曜?日?)\s*(.+)", text)
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

        schedule = {"type": "weekly", "weekday": weekday, "time": time_str}
        desc = f"毎週{weekday_text} {time_str}"
        return (schedule, desc)

    # Pattern 2: 毎月 DD日 時刻 (recurring monthly)
    match = re.match(r"毎月\s*(\d{1,2})日?\s*(.+)", text)
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

        schedule = {"type": "monthly", "day": day, "time": time_str}
        desc = f"毎月{day}日 {time_str}"
        return (schedule, desc)

    # Pattern 3: 来週○曜日 時刻
    match = re.match(r"来週\s*([月火水木金土日]曜?日?)\s*(.+)", text)
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
        target_time = target_time.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = (
            target_time.strftime("%Y年%m月%d日(%a) %H:%M")
            .replace("Mon", "月")
            .replace("Tue", "火")
            .replace("Wed", "水")
            .replace("Thu", "木")
            .replace("Fri", "金")
            .replace("Sat", "土")
            .replace("Sun", "日")
        )
        return (schedule, desc)

    # Pattern 4: 明後日 時刻
    match = re.match(r"明後日\s*(.+)", text)
    if match:
        time_part = match.group(1).replace("の", "").strip()

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        target_time = now + timedelta(days=2)
        target_time = target_time.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 5: 明日 時刻
    match = re.match(r"明日\s*(.+)", text)
    if match:
        time_part = match.group(1).replace("の", "").strip()

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        target_time = now + timedelta(days=1)
        target_time = target_time.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 6: 今日 時刻
    match = re.match(r"今日\s*(.+)", text)
    if match:
        time_part = match.group(1).replace("の", "").strip()

        time_tuple = parse_time_with_ampm(time_part)
        if time_tuple is None:
            return None

        hour, minute = time_tuple

        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If time has passed today, move to tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)

        schedule = {"type": "once", "run_at": target_time.isoformat()}
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

        schedule = {"type": "once", "run_at": target_time.isoformat()}
        desc = target_time.strftime("%Y年%m月%d日 %H:%M")
        return (schedule, desc)

    # Pattern 8: 日付のみ YYYY-MM-DD → デフォルト9:00
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))

        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
            schedule = {"type": "once", "run_at": target_time.isoformat()}
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 9: 日付のみ MM/DD → デフォルト9:00
    match = re.match(r"(\d{1,2})/(\d{1,2})$", text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year

        # If the date has passed this year, use next year
        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
            if target_time <= now:
                target_time = datetime(year + 1, month, day, 9, 0, tzinfo=TZ)

            schedule = {"type": "once", "run_at": target_time.isoformat()}
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 10: 日付のみ M月D日 → デフォルト9:00
    match = re.match(r"(\d{1,2})月(\d{1,2})日?$", text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year

        # If the date has passed this year, use next year
        try:
            target_time = datetime(year, month, day, 9, 0, tzinfo=TZ)
            if target_time <= now:
                target_time = datetime(year + 1, month, day, 9, 0, tzinfo=TZ)

            schedule = {"type": "once", "run_at": target_time.isoformat()}
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 11: YYYY年M月D日 (20XX年5月3日) → デフォルト9:00
    match = re.match(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?$", text)
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

            schedule = {"type": "once", "run_at": target_time.isoformat()}
            desc = target_time.strftime("%Y年%m月%d日 09:00")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 12: YYYY年M月D日 時刻付き (2025年5月3日 14:00)
    match = re.match(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?\s+(.+)", text)
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

            schedule = {"type": "once", "run_at": target_time.isoformat()}
            desc = target_time.strftime("%Y年%m月%d日 %H:%M")
            return (schedule, desc)
        except ValueError:
            return None

    # Pattern 13: YYYY-MM-DD HH:MM (structured format with time)
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})", text)
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

            schedule = {"type": "once", "run_at": target_time.isoformat()}
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
    return QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="10分後", text="10分後")),
            QuickReplyItem(action=MessageAction(label="30分後", text="30分後")),
            QuickReplyItem(action=MessageAction(label="1時間後", text="1時間後")),
            QuickReplyItem(action=MessageAction(label="明日9時", text="明日 9時")),
            QuickReplyItem(action=MessageAction(label="明日20時", text="明日 20時")),
            QuickReplyItem(
                action=MessageAction(label="毎週月曜20時", text="毎週月曜 20時")
            ),
            QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル")),
        ]
    )


def create_main_menu_quick_reply() -> QuickReply:
    """
    Create quick reply buttons for main menu.

    Returns:
        QuickReply object with main menu options.
    """
    return QuickReply(
        items=[
            QuickReplyItem(
                action=MessageAction(label="リマインド設定", text="リマインド設定")
            ),
            QuickReplyItem(
                action=MessageAction(label="リマインド一覧", text="リマインド一覧")
            ),
            QuickReplyItem(
                action=MessageAction(label="リマインド削除", text="リマインド削除")
            ),
        ]
    )


def create_delete_quick_reply(reminder_count: int) -> QuickReply:
    """
    Create quick reply buttons for reminder deletion.

    Args:
        reminder_count: Number of reminders to display buttons for

    Returns:
        QuickReply object with deletion options.
    """
    items = []

    # Add individual delete buttons (limit to first 10 reminders)
    display_count = min(reminder_count, 10)
    for i in range(1, display_count + 1):
        items.append(
            QuickReplyItem(action=MessageAction(label=f"{i}を削除", text=f"{i}"))
        )

    # Add "delete all" button
    items.append(
        QuickReplyItem(action=MessageAction(label="すべてを削除", text="すべてを削除"))
    )

    # Add cancel button
    items.append(
        QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル"))
    )

    return QuickReply(items=items)


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
        next_run = next_run.replace(
            hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0
        )

        return next_run.isoformat()

    elif schedule_type == "monthly":
        day = schedule.get("day")
        time_str = schedule.get("time")

        if day is None or time_str is None:
            return None

        now = get_current_time()
        target_time = datetime.strptime(time_str, "%H:%M").time()

        year = now.year
        month = now.month

        def build_run(y: int, m: int) -> datetime:
            return now.replace(
                year=y,
                month=m,
                day=day,
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0,
            )

        # Try current month if the day exists and time is in the future
        days_in_month = calendar.monthrange(year, month)[1]
        if day <= days_in_month:
            candidate = build_run(year, month)
            if candidate > now:
                return candidate.isoformat()

        # Otherwise, find the next month that contains the target day
        while True:
            month += 1
            if month > 12:
                month = 1
                year += 1

            if day > calendar.monthrange(year, month)[1]:
                continue

            candidate = build_run(year, month)
            if candidate > now:
                return candidate.isoformat()

    return None
