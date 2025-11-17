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
    print("Warning: python-dotenv not installed. Make sure environment variables are set.")

# Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
DATA_DIR = os.getenv('REMINDKUN_DATA_DIR', './data')
TIMEZONE = os.getenv('REMINDKUN_TIMEZONE', 'Asia/Tokyo')

if not LINE_CHANNEL_ACCESS_TOKEN:
    print("Error: LINE_CHANNEL_ACCESS_TOKEN must be set")
    sys.exit(1)

# Timezone object
TZ = ZoneInfo(TIMEZONE)

# LINE API endpoint
LINE_PUSH_MESSAGE_URL = "https://api.line.me/v2/bot/message/push"

# Setup logging (minimal output)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# JSON Storage Functions
# ============================================================================

def get_reminders_file_path() -> Path:
    """Get the path to the reminders JSON file."""
    return Path(DATA_DIR) / 'reminders.json'


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
        with open(file_path, 'r', encoding='utf-8') as f:
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
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving reminders: {e}")
        raise


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
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }

    payload = {
        'to': user_id,
        'messages': [
            {
                'type': 'text',
                'text': text
            }
        ]
    }

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


def calculate_next_run_at(schedule: Dict[str, Any], current_run: datetime) -> Optional[str]:
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
        next_run = next_run.replace(hour=target_time.hour, minute=target_time.minute,
                                     second=0, microsecond=0)

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
            next_run = next_run.replace(day=day, hour=target_time.hour,
                                        minute=target_time.minute, second=0, microsecond=0)
        except ValueError:
            # Day doesn't exist in this month, skip to next month
            if next_run.month == 12:
                next_run = next_run.replace(year=next_run.year + 1, month=1, day=day,
                                            hour=target_time.hour, minute=target_time.minute,
                                            second=0, microsecond=0)
            else:
                next_run = next_run.replace(month=next_run.month + 1, day=day,
                                            hour=target_time.hour, minute=target_time.minute,
                                            second=0, microsecond=0)

        return next_run.isoformat()

    return None


# ============================================================================
# Reminder Processing Functions
# ============================================================================

def process_due_reminders(reminders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process all due reminders and send notifications.

    Args:
        reminders: List of all reminders

    Returns:
        Updated list of reminders.
    """
    current_time = get_current_time()
    updated_reminders = []

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
            logger.error(f"Invalid next_run_at format for reminder {reminder.get('id')}: {e}")
            updated_reminders.append(reminder)
            continue

        # Check if due
        if next_run_at <= current_time:
            # Send notification
            user_id = reminder.get("user_id")
            text = reminder.get("text", "リマインダー")

            message = f"🔔 リマインダー\n{text}"

            success = send_line_push_message(user_id, message)

            if success:
                # Update reminder based on schedule type
                schedule = reminder.get("schedule", {})
                schedule_type = schedule.get("type")

                if schedule_type == "once":
                    # Mark as done
                    reminder["status"] = "done"
                else:
                    # Calculate next run time
                    next_run = calculate_next_run_at(schedule, next_run_at)
                    if next_run:
                        reminder["next_run_at"] = next_run
                    else:
                        # Couldn't calculate next run, mark as done
                        reminder["status"] = "done"
                        logger.warning(f"Couldn't calculate next run for reminder {reminder.get('id')}")

        updated_reminders.append(reminder)

    return updated_reminders


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
    """Main scheduler loop."""
    print("Starting Reminder Bot scheduler daemon")
    print(f"Data: {DATA_DIR} | TZ: {TIMEZONE} | Interval: 30s")

    while True:
        try:
            run_scheduler_cycle()
        except KeyboardInterrupt:
            print("\nScheduler stopped")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)

        # Sleep for 30 seconds before next cycle
        time.sleep(30)


if __name__ == "__main__":
    main()
