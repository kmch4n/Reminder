"""
session.py - User session management for interactive reminder registration
"""

from typing import Dict, Any, Optional

# Session storage (in-memory, lost on restart)
# Structure: {user_id: {"state": "waiting_for_time", "message": "text", "fail_count": 0}}
user_sessions: Dict[str, Dict[str, Any]] = {}

# Maximum number of failed attempts before clearing session
MAX_FAIL_COUNT = 5


# ============================================================================
# Session Management
# ============================================================================


def start_waiting_for_time_session(user_id: str, message: str) -> None:
    """Start a session waiting for time input."""
    user_sessions[user_id] = {
        "state": "waiting_for_time",
        "message": message,
        "fail_count": 0,
    }


def start_waiting_for_delete_id_session(user_id: str, reminders: list) -> None:
    """Start a session waiting for delete ID input."""
    user_sessions[user_id] = {
        "state": "waiting_for_delete_id",
        "reminders": reminders,
        "fail_count": 0,
    }


def start_waiting_for_delete_all_confirmation_session(user_id: str) -> None:
    """Start a session waiting for delete-all confirmation."""
    user_sessions[user_id] = {
        "state": "waiting_for_delete_all_confirmation",
        "fail_count": 0,
    }


def increment_fail_count(user_id: str) -> int:
    """Increment and return the fail count for a user session."""
    if user_id in user_sessions:
        user_sessions[user_id]["fail_count"] = (
            user_sessions[user_id].get("fail_count", 0) + 1
        )
        return user_sessions[user_id]["fail_count"]
    return 0


def get_user_session(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's current session."""
    return user_sessions.get(user_id)


def clear_user_session(user_id: str) -> None:
    """Clear user's session."""
    if user_id in user_sessions:
        del user_sessions[user_id]
