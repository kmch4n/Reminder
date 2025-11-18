#!/usr/bin/env python3
"""
send.py - Scheduler daemon for reminder bot

Periodically checks for due reminders and sends push messages
via LINE Messaging API.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

import requests

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
DATA_DIR = os.getenv("REMINDKUN_DATA_DIR", "./data")
TIMEZONE = os.getenv("REMINDKUN_TIMEZONE", "Asia/Tokyo")

if not LINE_CHANNEL_ACCESS_TOKEN:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN must be set")
    sys.exit(1)

# Timezone object
TZ = ZoneInfo(TIMEZONE)

# LINE API endpoint
LINE_PUSH_MESSAGE_URL = "https://api.line.me/v2/bot/message/push"

# Execution grace period (seconds)
# Reminders older than this will be archived without execution
EXECUTION_GRACE_PERIOD = 60

# Setup logging (minimal output)
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# JSON Storage Functions
# ============================================================================


def get_reminders_file_path() -> Path:
    """Get the path to the reminders JSON file."""
    return Path(DATA_DIR) / "reminders.json"


def get_archive_file_path() -> Path:
    """Get the path to the archive JSON file."""
    return Path(DATA_DIR) / "archive.json"


def load_reminders_from_file() -> List[Dict[str, Any]]:
    """
    Load all reminders from JSON file.

    Returns:
        List of reminder dictionaries.
    """
    file_path = get_reminders_file_path()

    if not file_path.exists():
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading reminders: {e}")
        return []


def save_reminders_to_file(reminders: List[Dict[str, Any]]) -> None:
    """
    Save all reminders to JSON file.

    Args:
        reminders: List of reminder dictionaries to save.
    """
    file_path = get_reminders_file_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving reminders: {e}")
        raise


def load_archive_from_file() -> List[Dict[str, Any]]:
    """
    Load archived reminders from JSON file.

    Returns:
        List of archived reminder dictionaries.
    """
    file_path = get_archive_file_path()

    if not file_path.exists():
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading archive: {e}")
        return []


def save_archive_to_file(archive: List[Dict[str, Any]]) -> None:
    """
    Save archived reminders to JSON file.

    Args:
        archive: List of archived reminder dictionaries to save.
    """
    file_path = get_archive_file_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(archive, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving archive: {e}")
        raise


def append_to_archive(completed_reminders: List[Dict[str, Any]]) -> None:
    """
    Append completed reminders to the archive file.

    Args:
        completed_reminders: List of completed reminder dictionaries to archive.
    """
    if not completed_reminders:
        return

    # Load existing archive
    archive = load_archive_from_file()

    # Add timestamp for when it was archived
    current_time = get_current_time()
    for reminder in completed_reminders:
        reminder["archived_at"] = current_time.isoformat()

    # Append new completed reminders
    archive.extend(completed_reminders)

    # Save updated archive
    save_archive_to_file(archive)


# ============================================================================
# LINE Messaging API Functions
# ============================================================================


def send_line_push_message(user_id: str, text: str) -> bool:
    """
    Send a push message to a LINE user.

    Args:
        user_id: LINE user ID
        text: Message text to send

    Returns:
        True if successful, False otherwise.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {"to": user_id, "messages": [{"type": "text", "text": text}]}

    try:
        response = requests.post(LINE_PUSH_MESSAGE_URL, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send push message: {e}")
        return False


# ============================================================================
# Time Calculation Functions
# ============================================================================


def get_current_time() -> datetime:
    """Get current time in configured timezone."""
    return datetime.now(TZ)


def calculate_next_run_at(
    schedule: Dict[str, Any], current_run: datetime
) -> Optional[str]:
    """
    Calculate the next run time for a recurring reminder.

    Args:
        schedule: Schedule dictionary
        current_run: Current run datetime

    Returns:
        ISO 8601 datetime string or None if not recurring.
    """
    schedule_type = schedule.get("type")

    if schedule_type == "once":
        # One-time reminders don't have a next run
        return None

    elif schedule_type == "weekly":
        weekday = schedule.get("weekday")
        time_str = schedule.get("time")

        if weekday is None or time_str is None:
            return None

        # Parse target time
        target_time = datetime.strptime(time_str, "%H:%M").time()

        # Calculate next week's occurrence
        next_run = current_run + timedelta(days=7)
        next_run = next_run.replace(
            hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0
        )

        return next_run.isoformat()

    elif schedule_type == "monthly":
        day = schedule.get("day")
        time_str = schedule.get("time")

        if day is None or time_str is None:
            return None

        # Parse target time
        target_time = datetime.strptime(time_str, "%H:%M").time()

        # Move to next month
        if current_run.month == 12:
            next_run = current_run.replace(year=current_run.year + 1, month=1)
        else:
            next_run = current_run.replace(month=current_run.month + 1)

        # Try to set the day
        try:
            next_run = next_run.replace(
                day=day,
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0,
            )
        except ValueError:
            # Day doesn't exist in this month, skip to next month
            if next_run.month == 12:
                next_run = next_run.replace(
                    year=next_run.year + 1,
                    month=1,
                    day=day,
                    hour=target_time.hour,
                    minute=target_time.minute,
                    second=0,
                    microsecond=0,
                )
            else:
                next_run = next_run.replace(
                    month=next_run.month + 1,
                    day=day,
                    hour=target_time.hour,
                    minute=target_time.minute,
                    second=0,
                    microsecond=0,
                )

        return next_run.isoformat()

    return None


# ============================================================================
# Reminder Processing Functions
# ============================================================================


def process_due_reminders(reminders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process all due reminders and send notifications.

    Completed reminders are moved to archive.json.

    Args:
        reminders: List of all reminders

    Returns:
        Updated list of active reminders (excluding completed ones).
    """
    current_time = get_current_time()
    updated_reminders = []
    completed_reminders = []

    for reminder in reminders:
        # Skip if not pending
        if reminder.get("status") != "pending":
            updated_reminders.append(reminder)
            continue

        # Parse next_run_at
        next_run_at_str = reminder.get("next_run_at")
        if not next_run_at_str:
            updated_reminders.append(reminder)
            continue

        try:
            next_run_at = datetime.fromisoformat(next_run_at_str)
        except ValueError as e:
            logger.error(
                f"Invalid next_run_at format for reminder {reminder.get('id')}: {e}"
            )
            updated_reminders.append(reminder)
            continue

        # Check if due
        if next_run_at <= current_time:
            # Calculate how long overdue this reminder is
            time_diff = (current_time - next_run_at).total_seconds()

            # If reminder is too old, archive it without executing
            if time_diff > EXECUTION_GRACE_PERIOD:
                reminder["status"] = "done"
                completed_reminders.append(reminder)
                logger.warning(
                    f"Reminder {reminder.get('id')} is {int(time_diff)}s overdue, archiving without execution"
                )
                continue

            # Send notification (only if within grace period)
            user_id = reminder.get("user_id")
            text = reminder.get("text", "リマインダー")

            message = f"🔔 リマインダー\n{text}"

            success = send_line_push_message(user_id, message)

            if success:
                # Update reminder based on schedule type
                schedule = reminder.get("schedule", {})
                schedule_type = schedule.get("type")

                if schedule_type == "once":
                    # Mark as done and move to archive
                    reminder["status"] = "done"
                    completed_reminders.append(reminder)
                else:
                    # Calculate next run time
                    next_run = calculate_next_run_at(schedule, next_run_at)
                    if next_run:
                        reminder["next_run_at"] = next_run
                        updated_reminders.append(reminder)
                    else:
                        # Couldn't calculate next run, mark as done and archive
                        reminder["status"] = "done"
                        completed_reminders.append(reminder)
                        logger.warning(
                            f"Couldn't calculate next run for reminder {reminder.get('id')}"
                        )
            else:
                # Failed to send, keep for retry
                updated_reminders.append(reminder)
        else:
            # Not due yet, keep it
            updated_reminders.append(reminder)

    # Move completed reminders to archive
    if completed_reminders:
        append_to_archive(completed_reminders)

    return updated_reminders


def get_next_reminder_time(reminders: List[Dict[str, Any]]) -> Optional[datetime]:
    """
    Get the earliest next_run_at time from pending reminders.

    Args:
        reminders: List of all reminders

    Returns:
        Datetime of next reminder, or None if no pending reminders.
    """
    next_time = None
    for reminder in reminders:
        if reminder.get("status") != "pending":
            continue
        next_run_at_str = reminder.get("next_run_at")
        if not next_run_at_str:
            continue
        try:
            next_run_at = datetime.fromisoformat(next_run_at_str)
            if next_time is None or next_run_at < next_time:
                next_time = next_run_at
        except ValueError:
            continue
    return next_time


def calculate_sleep_duration(reminders: List[Dict[str, Any]]) -> float:
    """
    Calculate optimal sleep duration based on next reminder.

    Strategy:
    - No reminders or next reminder > 30s away: sleep 30s (reduce load)
    - Next reminder < 30s away: sleep until that time (increase precision)

    Args:
        reminders: List of all reminders

    Returns:
        Sleep duration in seconds.
    """
    next_reminder = get_next_reminder_time(reminders)

    if next_reminder is None:
        # No pending reminders, use default interval
        return 30.0

    now = get_current_time()
    time_until_next = (next_reminder - now).total_seconds()

    if time_until_next <= 0:
        # Reminder is due now, check immediately
        return 0.5
    elif time_until_next < 30:
        # Reminder is soon, sleep until then (with small buffer)
        return max(0.5, time_until_next)
    else:
        # Reminder is far away, use default interval
        return 30.0


def run_scheduler_cycle() -> None:
    """
    Run one cycle of the scheduler.

    Loads reminders, processes due ones, and saves updates.
    """
    try:
        # Load reminders
        reminders = load_reminders_from_file()

        # Process due reminders
        updated_reminders = process_due_reminders(reminders)

        # Save updated reminders
        save_reminders_to_file(updated_reminders)

    except Exception as e:
        logger.error(f"Error in scheduler cycle: {e}", exc_info=True)


# ============================================================================
# Main Loop
# ============================================================================


def main():
    """Main scheduler loop with adaptive sleep."""
    print("Starting Reminder Bot scheduler daemon")
    print(f"Data: {DATA_DIR} | TZ: {TIMEZONE} | Adaptive interval: max 30s")

    while True:
        try:
            run_scheduler_cycle()

            # Load reminders to calculate optimal sleep duration
            reminders = load_reminders_from_file()
            sleep_duration = calculate_sleep_duration(reminders)

            # Sleep with adaptive duration
            time.sleep(sleep_duration)

        except KeyboardInterrupt:
            print("\nScheduler stopped")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            # Fallback to default interval on error
            time.sleep(30)


if __name__ == "__main__":
    main()
