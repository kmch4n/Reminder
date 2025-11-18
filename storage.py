"""
storage.py - JSON file storage operations for reminders
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

# Configuration
DATA_DIR = os.getenv("REMINDER_DATA_DIR", "./data")

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# JSON Storage Functions
# ============================================================================


def get_reminders_file_path() -> Path:
    """Get the path to the reminders JSON file."""
    return Path(DATA_DIR) / "reminders.json"


def load_reminders_from_file() -> List[Dict[str, Any]]:
    """Load all reminders from JSON file."""
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
    """Save all reminders to JSON file."""
    file_path = get_reminders_file_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Error saving reminders: {e}")
        raise


def add_reminder_to_file(reminder: Dict[str, Any]) -> None:
    """Add a new reminder to the JSON file."""
    reminders = load_reminders_from_file()
    reminders.append(reminder)
    save_reminders_to_file(reminders)
