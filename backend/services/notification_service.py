"""Notification Service — AOCC timeline feed (newest first)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.models import NotificationEvent

logger = logging.getLogger(__name__)

_MAX_EVENTS = 80
_lock = threading.Lock()
_events: list[NotificationEvent] = []


class NotificationService:
    """In-memory notification feed for the AOCC dashboard."""

    def add(
        self,
        message: str,
        *,
        category: str = "ops",
        severity: Optional[str] = None,
    ) -> NotificationEvent:
        event = NotificationEvent(
            id=f"evt_{uuid.uuid4().hex[:10]}",
            time=datetime.now(timezone.utc),
            message=message,
            category=category,
            severity=severity,
        )
        with _lock:
            _events.insert(0, event)
            del _events[_MAX_EVENTS:]
        logger.debug("Notification: %s", message)
        return event

    def list_events(self, limit: int = 30) -> list[dict]:
        with _lock:
            rows = list(_events)[: max(1, min(limit, _MAX_EVENTS))]
        return [
            {
                "id": e.id,
                "time": e.time.isoformat(),
                "message": e.message,
                "category": e.category,
                "severity": e.severity,
            }
            for e in rows
        ]


_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
