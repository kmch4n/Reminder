"""Guard LINE webhook processing against stale and duplicate events."""

import time
from collections import OrderedDict
from threading import Lock
from typing import Optional


class WebhookEventGuard:
    """Track recently processed webhook events and reject stale redeliveries."""

    def __init__(
        self,
        max_event_ids: int = 2048,
        max_redelivery_age_milliseconds: int = 20 * 60 * 1000,
    ) -> None:
        self._max_event_ids = max_event_ids
        self._max_redelivery_age_milliseconds = max_redelivery_age_milliseconds
        self._processed_event_ids: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    def should_process(
        self,
        event_id: Optional[str],
        event_timestamp_milliseconds: int,
        is_redelivery: bool,
        current_timestamp_milliseconds: Optional[int] = None,
    ) -> bool:
        """Return whether an event is fresh and has not been processed before."""
        if current_timestamp_milliseconds is None:
            current_timestamp_milliseconds = int(time.time() * 1000)

        event_age = current_timestamp_milliseconds - event_timestamp_milliseconds
        if is_redelivery and event_age > self._max_redelivery_age_milliseconds:
            return False

        if not event_id:
            return True

        with self._lock:
            if event_id in self._processed_event_ids:
                return False

            self._processed_event_ids[event_id] = None
            if len(self._processed_event_ids) > self._max_event_ids:
                self._processed_event_ids.popitem(last=False)

        return True
