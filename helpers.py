"""
helpers.py - Reminder creation and display utilities
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

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


def create_reminder_list_flex(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Create Flex Message for reminder list display (Design 2).
    Creates separate bubbles for each schedule type (once, weekly, monthly).

    Args:
        user_id: LINE user ID

    Returns:
        Flex Message contents dict (Carousel) or None if no reminders.
    """
    reminders = load_reminders_from_file()
    user_reminders = [
        r
        for r in reminders
        if r.get("user_id") == user_id and r.get("status") == "pending"
    ]

    if not user_reminders:
        return None

    # Group reminders by schedule type
    reminders_by_type = {
        "once": [],
        "weekly": [],
        "monthly": [],
    }

    for reminder in user_reminders:
        schedule_type = reminder.get("schedule", {}).get("type", "once")
        if schedule_type in reminders_by_type:
            reminders_by_type[schedule_type].append(reminder)

    # Sort each group by next_run_at
    for schedule_type in reminders_by_type:
        reminders_by_type[schedule_type].sort(key=lambda r: r.get("next_run_at", ""))

    # Build bubbles for each schedule type
    bubbles = []

    # Helper function to create a bubble for a schedule type
    def create_bubble(schedule_type: str, reminders_list: list) -> Dict[str, Any]:
        if schedule_type == "once":
            title = "⏰ 一度きり"
            header_color = "#2d5016"
            bar_color = "#70AD47"
            type_icon = "⏰"
        elif schedule_type == "weekly":
            title = "🔁 毎週"
            header_color = "#1e3a5f"
            bar_color = "#5B9BD5"
            type_icon = "🔁"
        else:  # monthly
            title = "📅 毎月"
            header_color = "#5f2d11"
            bar_color = "#ED7D31"
            type_icon = "📅"

        # Build reminder items
        body_contents = []

        for i, reminder in enumerate(reminders_list, 1):
            text = reminder.get("text", "")
            next_run_at_str = reminder.get("next_run_at", "")

            # Format datetime
            try:
                next_run_at = datetime.fromisoformat(next_run_at_str)
                date_str = next_run_at.strftime("%m/%d")
                weekday_str = next_run_at.strftime("(%a)")
                time_str = next_run_at.strftime("%H:%M")
            except (ValueError, AttributeError):
                date_str = "不明"
                weekday_str = ""
                time_str = ""

            # Create reminder box with left color bar
            reminder_box = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    # Left color bar
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [],
                        "width": "5px",
                        "backgroundColor": bar_color,
                    },
                    # Content
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            # Icon and date/time row
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": type_icon,
                                        "size": "md",
                                        "flex": 0,
                                    },
                                    {
                                        "type": "text",
                                        "text": f"{date_str} {weekday_str} {time_str}",
                                        "size": "sm",
                                        "weight": "bold",
                                        "color": "#ffffff",
                                        "margin": "sm",
                                    },
                                ],
                            },
                            # Separator
                            {
                                "type": "separator",
                                "margin": "md",
                                "color": "#404040",
                            },
                            # Message
                            {
                                "type": "text",
                                "text": text,
                                "size": "md",
                                "color": "#e0e0e0",
                                "wrap": True,
                                "margin": "md",
                            },
                        ],
                        "paddingAll": "12px",
                        "flex": 1,
                    },
                ],
                "backgroundColor": "#2c2c2c",
                "cornerRadius": "8px",
                "margin": "sm" if i > 1 else "none",
            }

            body_contents.append(reminder_box)

        # Build bubble
        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": title,
                        "size": "xl",
                        "weight": "bold",
                        "color": "#ffffff",
                    }
                ],
                "backgroundColor": header_color,
                "paddingAll": "18px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents,
                "paddingAll": "12px",
                "backgroundColor": "#1a1a1a",
            },
        }

    # Create bubbles in order: once, weekly, monthly
    for schedule_type in ["once", "weekly", "monthly"]:
        if reminders_by_type[schedule_type]:
            bubbles.append(
                create_bubble(schedule_type, reminders_by_type[schedule_type])
            )

    # Return Carousel if multiple bubbles, otherwise single bubble
    if len(bubbles) == 1:
        return bubbles[0]
    else:
        return {
            "type": "carousel",
            "contents": bubbles,
        }


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


def create_reminder_deletion_flex(user_id: str) -> Optional[tuple]:
    """
    Create Flex Message for reminder deletion list.
    Similar to create_reminder_list_flex but with deletion-focused design.

    Args:
        user_id: LINE user ID

    Returns:
        Tuple of (Flex Message contents dict or None, list of reminders) if reminders exist.
        None if no reminders.
    """
    reminders = load_reminders_from_file()
    user_reminders = [
        r
        for r in reminders
        if r.get("user_id") == user_id and r.get("status") == "pending"
    ]

    if not user_reminders:
        return None

    # Sort by next_run_at (will be used for numbering)
    user_reminders.sort(key=lambda r: r.get("next_run_at", ""))

    # Group reminders by schedule type (while maintaining sort order)
    reminders_by_type = {
        "once": [],
        "weekly": [],
        "monthly": [],
    }

    # Track global index for numbering
    for i, reminder in enumerate(user_reminders, 1):
        schedule_type = reminder.get("schedule", {}).get("type", "once")
        if schedule_type in reminders_by_type:
            # Store reminder with its global number
            reminders_by_type[schedule_type].append((i, reminder))

    # Build bubbles for each schedule type
    bubbles = []

    # Helper function to create a bubble for a schedule type
    def create_bubble(
        schedule_type: str, reminders_with_numbers: list
    ) -> Dict[str, Any]:
        if schedule_type == "once":
            title = "⏰ 一度きり"
            header_color = "#5f1111"  # Darker red for deletion
            bar_color = "#E74C3C"  # Red for deletion
            type_icon = "⏰"
        elif schedule_type == "weekly":
            title = "🔁 毎週"
            header_color = "#5f1111"
            bar_color = "#E74C3C"
            type_icon = "🔁"
        else:  # monthly
            title = "📅 毎月"
            header_color = "#5f1111"
            bar_color = "#E74C3C"
            type_icon = "📅"

        # Build reminder items
        body_contents = []

        for number, reminder in reminders_with_numbers:
            text = reminder.get("text", "")
            next_run_at_str = reminder.get("next_run_at", "")

            # Format datetime
            try:
                next_run_at = datetime.fromisoformat(next_run_at_str)
                date_str = next_run_at.strftime("%m/%d")
                weekday_str = next_run_at.strftime("(%a)")
                time_str = next_run_at.strftime("%H:%M")
            except (ValueError, AttributeError):
                date_str = "不明"
                weekday_str = ""
                time_str = ""

            # Create reminder box with number badge and left color bar
            reminder_box = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    # Left color bar
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [],
                        "width": "5px",
                        "backgroundColor": bar_color,
                    },
                    # Content
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            # Number badge and date/time row
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    # Number badge
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": str(number),
                                                "size": "md",
                                                "weight": "bold",
                                                "color": "#ffffff",
                                                "align": "center",
                                            }
                                        ],
                                        "backgroundColor": bar_color,
                                        "cornerRadius": "15px",
                                        "width": "30px",
                                        "height": "30px",
                                        "justifyContent": "center",
                                        "flex": 0,
                                    },
                                    # Icon and date/time
                                    {
                                        "type": "box",
                                        "layout": "horizontal",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": type_icon,
                                                "size": "md",
                                                "flex": 0,
                                            },
                                            {
                                                "type": "text",
                                                "text": f"{date_str} {weekday_str} {time_str}",
                                                "size": "sm",
                                                "weight": "bold",
                                                "color": "#ffffff",
                                                "margin": "sm",
                                            },
                                        ],
                                        "margin": "md",
                                    },
                                ],
                            },
                            # Separator
                            {
                                "type": "separator",
                                "margin": "md",
                                "color": "#404040",
                            },
                            # Message
                            {
                                "type": "text",
                                "text": text,
                                "size": "md",
                                "color": "#e0e0e0",
                                "wrap": True,
                                "margin": "md",
                            },
                        ],
                        "paddingAll": "12px",
                        "flex": 1,
                    },
                ],
                "backgroundColor": "#2c2c2c",
                "cornerRadius": "8px",
                "margin": "sm" if body_contents else "none",
            }

            body_contents.append(reminder_box)

        # Build bubble
        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": title,
                        "size": "xl",
                        "weight": "bold",
                        "color": "#ffffff",
                    }
                ],
                "backgroundColor": header_color,
                "paddingAll": "18px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents,
                "paddingAll": "12px",
                "backgroundColor": "#1a1a1a",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "削除する番号を送信してください",
                        "size": "xs",
                        "color": "#999999",
                        "align": "center",
                    }
                ],
                "backgroundColor": "#1a1a1a",
                "paddingAll": "12px",
            },
        }

    # Create bubbles in order: once, weekly, monthly
    for schedule_type in ["once", "weekly", "monthly"]:
        if reminders_by_type[schedule_type]:
            bubbles.append(
                create_bubble(schedule_type, reminders_by_type[schedule_type])
            )

    # Return Carousel if multiple bubbles, otherwise single bubble
    if len(bubbles) == 1:
        flex_contents = bubbles[0]
    else:
        flex_contents = {
            "type": "carousel",
            "contents": bubbles,
        }

    return (flex_contents, user_reminders)


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
