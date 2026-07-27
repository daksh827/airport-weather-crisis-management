"""Domain models for AOCC Incident & Crisis Management (Phase 6A)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    """Operational severity for an airport incident."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class IncidentStatus(str, Enum):
    """Lifecycle status for an airport incident."""

    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class Incident(BaseModel):
    """Single AOCC incident record."""

    incident_id: str = Field(..., description="Unique incident identifier")
    incident_type: str
    severity: IncidentSeverity
    airport_area: str
    assigned_department: str
    status: IncidentStatus
    created_time: datetime
    last_updated: datetime
    description: Optional[str] = None
    icao_code: str = "VIDP"
