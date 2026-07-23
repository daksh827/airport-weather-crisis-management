"""Operations impact and notification API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import success_response
from backend.services.impact_service import ImpactService, get_impact_service
from backend.services.notification_service import NotificationService, get_notification_service

logger = logging.getLogger(__name__)

operations_router = APIRouter(prefix="/operations", tags=["Operations"])
notifications_router = APIRouter(tags=["Notifications"])


@operations_router.get("/impact")
def get_operations_impact(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    impact_service: ImpactService = Depends(get_impact_service),
):
    """Return AOCC operational impact assessment from live weather."""
    data = impact_service.get_impact(icao)
    return success_response(data, message="Operational impact assessed successfully")


@notifications_router.get("/notifications")
def get_notifications(
    limit: int = Query(default=30, ge=1, le=80),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Return AOCC notification timeline (newest first)."""
    data = {"items": notification_service.list_events(limit=limit)}
    return success_response(data, message="Notifications retrieved successfully")
