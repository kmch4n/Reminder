"""
helpers.py - Reminder creation and display utilities
"""

import uuid
from datetime import datetime
from typing import Dict, Any

from storage import load_reminders_from_file
from time_parser import calculate_initial_run_at, get_current_time


# ============================================================================
# Reminder Creation
# ============================================================================


def create_reminder_object(
    user_id: str, message: str, schedule: Dict[str, Any]
) -> Dict[str, Any]:
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
        "status": "pending",
    }


# ============================================================================
# Reminder List Display
# ============================================================================


def format_reminder_list(user_id: str) -> str:
    """
    Format and return user's reminder list.

    Args:
        user_id: LINE user ID

    Returns:
        Formatted reminder list text.
    """
    reminders = load_reminders_from_file()
    user_reminders = [
        r
        for r in reminders
        if r.get("user_id") == user_id and r.get("status") == "pending"
    ]

    if not user_reminders:
        return "📋 登録されているリマインダーはありません。"

    # Sort by next_run_at
    user_reminders.sort(key=lambda r: r.get("next_run_at", ""))

    lines = ["📋 リマインダー一覧\n"]

    for i, reminder in enumerate(user_reminders, 1):
        text = reminder.get("text", "")
        next_run_at_str = reminder.get("next_run_at", "")
        schedule = reminder.get("schedule", {})
        schedule_type = schedule.get("type", "")

        # Format datetime
        try:
            next_run_at = datetime.fromisoformat(next_run_at_str)
            time_str = next_run_at.strftime("%m/%d %H:%M")
        except (ValueError, AttributeError):
            time_str = "不明"

        # Add schedule type indicator
        if schedule_type == "weekly":
            type_indicator = "🔁 毎週"
        elif schedule_type == "monthly":
            type_indicator = "🔁 毎月"
        else:
            type_indicator = "📅"

        lines.append(f"{i}. {type_indicator} {time_str}")
        lines.append(f"   {text}\n")

    return "\n".join(lines)


def format_reminder_list_for_deletion(user_id: str) -> tuple:
    """
    Format user's reminder list for deletion with numbered IDs.

    Args:
        user_id: LINE user ID

    Returns:
        Tuple of (formatted text, list of reminders).
    """
    reminders = load_reminders_from_file()
    user_reminders = [
        r
        for r in reminders
        if r.get("user_id") == user_id and r.get("status") == "pending"
    ]

    if not user_reminders:
        return ("📋 削除できるリマインダーはありません。", [])

    # Sort by next_run_at
    user_reminders.sort(key=lambda r: r.get("next_run_at", ""))

    lines = ["📋 削除するリマインダーの番号を送信してください\n"]

    for i, reminder in enumerate(user_reminders, 1):
        text = reminder.get("text", "")
        next_run_at_str = reminder.get("next_run_at", "")
        schedule = reminder.get("schedule", {})
        schedule_type = schedule.get("type", "")

        # Format datetime
        try:
            next_run_at = datetime.fromisoformat(next_run_at_str)
            time_str = next_run_at.strftime("%m/%d %H:%M")
        except (ValueError, AttributeError):
            time_str = "不明"

        # Add schedule type indicator
        if schedule_type == "weekly":
            type_indicator = "🔁 毎週"
        elif schedule_type == "monthly":
            type_indicator = "🔁 毎月"
        else:
            type_indicator = "📅"

        lines.append(f"{i}. {type_indicator} {time_str}")
        lines.append(f"   {text}\n")

    lines.append("\n削除をやめる場合は「キャンセル」と送信してください。")

    return ("\n".join(lines), user_reminders)


def delete_reminder_by_id(reminder_id: str) -> bool:
    """
    Delete a reminder by its ID.

    Args:
        reminder_id: Reminder ID to delete

    Returns:
        True if deleted successfully, False otherwise.
    """
    reminders = load_reminders_from_file()
    original_count = len(reminders)

    # Filter out the reminder to delete
    reminders = [r for r in reminders if r.get("id") != reminder_id]

    if len(reminders) < original_count:
        from storage import save_reminders_to_file

        save_reminders_to_file(reminders)
        return True
    return False


def delete_all_reminders(user_id: str) -> int:
    """
    Delete all reminders for a user.

    Args:
        user_id: LINE user ID

    Returns:
        Number of reminders deleted.
    """
    reminders = load_reminders_from_file()
    original_count = len(reminders)

    # Filter out all reminders for this user (only pending ones)
    reminders = [
        r
        for r in reminders
        if not (r.get("user_id") == user_id and r.get("status") == "pending")
    ]

    deleted_count = original_count - len(reminders)

    if deleted_count > 0:
        from storage import save_reminders_to_file

        save_reminders_to_file(reminders)

    return deleted_count
