"""
notification_history.py - Track last notifications per user for snooze feature.
"""

import json
import os
import fcntl
from pathlib import Path
from typing import Dict, Any, Optional

# Configuration
DATA_DIR = os.getenv("REMINDER_DATA_DIR", "./data")
FILE_PATH = Path(DATA_DIR) / "last_notifications.json"


def _read_file() -> Dict[str, Any]:
    """Read last notification data with a shared lock."""
    if not FILE_PATH.exists():
        return {}

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _write_file(data: Dict[str, Any]) -> None:
    """Write last notification data with an exclusive lock."""
    FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(FILE_PATH, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def get_last_notification(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the last notification record for a user."""
    data = _read_file()
    record = data.get(user_id)
    if record is None:
        return None
    return record.copy()


def set_last_notification(user_id: str, record: Dict[str, Any]) -> None:
    """Persist the last notification record for a user."""
    data = _read_file()
    data[user_id] = record
    _write_file(data)


def clear_last_notification(user_id: str) -> None:
    """Remove last notification record for a user."""
    data = _read_file()
    if user_id in data:
        del data[user_id]
        _write_file(data)
