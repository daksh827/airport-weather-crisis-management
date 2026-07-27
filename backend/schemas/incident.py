"""API schemas for AOCC Incident Management (Phase 6A)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IncidentItem(BaseModel):
    """Incident row returned by GET /api/incidents."""

    incident_id: str
    incident_type: str
    severity: str
    airport_area: str
    assigned_department: str
    status: str
    created_time: datetime
    last_updated: datetime
    description: Optional[str] = None
    icao_code: str = "VIDP"


class IncidentListData(BaseModel):
    """Envelope data for the incident list endpoint."""

    items: list[IncidentItem] = Field(default_factory=list)
    total: int = 0


class IncidentStatsData(BaseModel):
    """Envelope data for GET /api/incidents/stats."""

    open_incidents: int = 0
    assigned: int = 0
    in_progress: int = 0
    resolved_today: int = 0
    closed_today: int = 0
