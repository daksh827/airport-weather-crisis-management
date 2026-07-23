"""Weather alert API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import success_response
from backend.services.alert_service import AlertService, get_alert_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/current")
def get_current_alert(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Return the current primary weather alert, checklist, and trends."""
    data = alert_service.get_current(icao)
    return success_response(data, message="Current weather alert retrieved successfully")


@router.get("/history")
def get_alert_history(
    limit: int = Query(default=50, ge=1, le=100),
    alert_service: AlertService = Depends(get_alert_service),
):
    """Return runtime alert history (newest first)."""
    data = {"items": alert_service.get_history(limit=limit)}
    return success_response(data, message="Alert history retrieved successfully")
