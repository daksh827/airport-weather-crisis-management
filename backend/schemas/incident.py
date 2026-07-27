"""API schemas for AOCC Incident Management (Phase 6A/6B)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IncidentItem(BaseModel):
    """Incident row returned by incident APIs."""

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


class CreateIncidentRequest(BaseModel):
    """Payload for POST /api/incidents."""

    incident_type: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    severity: str = Field(..., min_length=1, max_length=40)
    airport_area: str = Field(..., min_length=1, max_length=120)
    icao_code: Optional[str] = Field(default=None, max_length=8)


class UpdateIncidentRequest(BaseModel):
    """Payload for PUT /api/incidents/{id} — editable fields only."""

    status: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    airport_area: Optional[str] = Field(default=None, min_length=1, max_length=120)
