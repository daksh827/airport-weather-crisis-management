"""Incident Management Service — Phase 6A foundation with mock data."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.models.incident import Incident, IncidentSeverity, IncidentStatus

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentService:
    """Provides mock AOCC incident list and statistics for Phase 6A."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._incidents = self._build_mock_incidents()

    def list_incidents(self, icao_code: Optional[str] = None) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()
        items = [
            self._to_dict(item)
            for item in self._incidents
            if item.icao_code == icao
        ]
        data = {"items": items, "total": len(items)}
        logger.info("Incident list for %s: %s row(s)", icao, len(items))
        return data

    def get_stats(self, icao_code: Optional[str] = None) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()
        # Phase 6A: fixed mock statistics for dashboard cards
        data = {
            "open_incidents": 4,
            "assigned": 2,
            "in_progress": 3,
            "resolved_today": 1,
            "closed_today": 0,
            "icao_code": icao,
            "last_updated": _utc_now().isoformat(),
        }
        logger.info(
            "Incident stats for %s: open=%s assigned=%s in_progress=%s",
            icao,
            data["open_incidents"],
            data["assigned"],
            data["in_progress"],
        )
        return data

    def _build_mock_incidents(self) -> list[Incident]:
        now = _utc_now()
        icao = self.settings.airport_icao.upper()
        return [
            Incident(
                incident_id="INC-2026-001",
                incident_type="Low Visibility",
                severity=IncidentSeverity.HIGH,
                airport_area="Runway 09/27",
                assigned_department="ATC",
                status=IncidentStatus.IN_PROGRESS,
                created_time=now - timedelta(hours=2, minutes=15),
                last_updated=now - timedelta(minutes=18),
                description="Reduced visibility impacting arrival acceptance rate.",
                icao_code=icao,
            ),
            Incident(
                incident_id="INC-2026-002",
                incident_type="Ground Equipment Shortage",
                severity=IncidentSeverity.MEDIUM,
                airport_area="Apron / Terminal 3",
                assigned_department="Ground Ops",
                status=IncidentStatus.ASSIGNED,
                created_time=now - timedelta(hours=1, minutes=40),
                last_updated=now - timedelta(minutes=35),
                description="Pushback and fuel truck availability constrained.",
                icao_code=icao,
            ),
            Incident(
                incident_id="INC-2026-003",
                incident_type="Passenger Congestion",
                severity=IncidentSeverity.MEDIUM,
                airport_area="Terminal 2 Security",
                assigned_department="Terminal",
                status=IncidentStatus.OPEN,
                created_time=now - timedelta(minutes=55),
                last_updated=now - timedelta(minutes=55),
                description="Security queue elevated due to weather delays.",
                icao_code=icao,
            ),
            Incident(
                incident_id="INC-2026-004",
                incident_type="Weather Watch",
                severity=IncidentSeverity.LOW,
                airport_area="Airport-wide",
                assigned_department="AOCC",
                status=IncidentStatus.RESOLVED,
                created_time=now - timedelta(hours=5),
                last_updated=now - timedelta(hours=1),
                description="Fog watch monitored and cleared for morning bank.",
                icao_code=icao,
            ),
        ]

    @staticmethod
    def _to_dict(incident: Incident) -> dict:
        payload = incident.model_dump()
        payload["severity"] = incident.severity.value
        payload["status"] = incident.status.value
        payload["created_time"] = incident.created_time.isoformat()
        payload["last_updated"] = incident.last_updated.isoformat()
        return payload


def get_incident_service() -> IncidentService:
    return IncidentService()
