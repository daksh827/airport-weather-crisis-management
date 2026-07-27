"""Incident Management API routes (Phase 6A)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import success_response
from backend.services.incident_service import IncidentService, get_incident_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("/stats")
def get_incident_stats(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Return mock incident statistics for dashboard cards."""
    data = incident_service.get_stats(icao)
    return success_response(data, message="Incident statistics retrieved successfully")


@router.get("")
def list_incidents(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Return mock AOCC incident records for the dashboard table."""
    data = incident_service.list_incidents(icao)
    return success_response(data, message="Incidents retrieved successfully")
