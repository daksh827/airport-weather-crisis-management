"""Incident Management Service — Phase 6A mock data + Phase 6B CRUD workflow."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.models.incident import Incident, IncidentSeverity, IncidentStatus

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_incident_service: Optional["IncidentService"] = None

# Create-form severities (Phase 6B). Legacy Low/Medium/High/Critical remain valid for mocks.
_CREATE_SEVERITIES = {
    IncidentSeverity.LEVEL_1.value,
    IncidentSeverity.LEVEL_2.value,
    IncidentSeverity.LEVEL_3.value,
}

_STATUS_VALUES = {s.value for s in IncidentStatus}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def assign_department(incident_type: str, airport_area: str) -> str:
    """Auto-assign department from incident type and airport area keywords."""
    text = f"{incident_type} {airport_area}".lower()

    rules = (
        (("medical", "ambulance", "injury", "casualty"), "Airport Medical Team"),
        (("security", "breach", "unlawful"), "Airport Security"),
        (("fire", "smoke", "rescue"), "Airport Fire Service"),
        (("engineering", "equipment failure", "electrical", "hvac"), "Engineering"),
        (
            ("ground equipment", "pushback", "fuel truck", "baggage cart", "gse"),
            "Ground Operations",
        ),
        (
            ("passenger", "congestion", "terminal", "boarding", "queue"),
            "Terminal Operations",
        ),
        (
            (
                "thunderstorm",
                "heavy rain",
                "dense fog",
                "strong wind",
                "weather",
                "visibility",
                "fog",
                "rain",
                "wind",
                "storm",
            ),
            "Meteorology",
        ),
        (("runway", "taxiway", "flight delay", "runway closure", "atc"), "ATC"),
        (("apron", "cargo", "ramp"), "Ground Operations"),
    )

    for keywords, department in rules:
        if any(keyword in text for keyword in keywords):
            return department

    return "AOCC"


class IncidentService:
    """In-memory AOCC incident store with create / update / delete workflow."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._incidents = self._build_mock_incidents()
        self._seq = self._next_sequence_seed()

    def list_incidents(self, icao_code: Optional[str] = None) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()
        with _lock:
            items = [
                self._to_dict(item)
                for item in self._incidents
                if item.icao_code == icao
            ]
        # Newest first for operator visibility
        items.sort(key=lambda row: row.get("created_time") or "", reverse=True)
        data = {"items": items, "total": len(items)}
        logger.info("Incident list for %s: %s row(s)", icao, len(items))
        return data

    def get_stats(self, icao_code: Optional[str] = None) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()
        today = _utc_now().date()

        with _lock:
            scoped = [item for item in self._incidents if item.icao_code == icao]
            open_count = sum(1 for i in scoped if i.status == IncidentStatus.OPEN)
            assigned = sum(1 for i in scoped if i.status == IncidentStatus.ASSIGNED)
            in_progress = sum(1 for i in scoped if i.status == IncidentStatus.IN_PROGRESS)
            resolved_today = sum(
                1
                for i in scoped
                if i.status == IncidentStatus.RESOLVED
                and i.last_updated.astimezone(timezone.utc).date() == today
            )
            closed_today = sum(
                1
                for i in scoped
                if i.status == IncidentStatus.CLOSED
                and i.last_updated.astimezone(timezone.utc).date() == today
            )

        data = {
            "open_incidents": open_count,
            "assigned": assigned,
            "in_progress": in_progress,
            "resolved_today": resolved_today,
            "closed_today": closed_today,
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

    def create_incident(
        self,
        *,
        incident_type: str,
        description: str,
        severity: str,
        airport_area: str,
        icao_code: Optional[str] = None,
    ) -> dict:
        incident_type = (incident_type or "").strip()
        description = (description or "").strip()
        airport_area = (airport_area or "").strip()
        severity_raw = (severity or "").strip()

        if not incident_type:
            raise ValueError("Incident Type is required")
        if not description:
            raise ValueError("Description is required")
        if not airport_area:
            raise ValueError("Airport Area is required")
        if severity_raw not in _CREATE_SEVERITIES and severity_raw not in {
            s.value for s in IncidentSeverity
        }:
            raise ValueError("Severity must be Level 1, Level 2, or Level 3")

        try:
            severity_enum = IncidentSeverity(severity_raw)
        except ValueError as exc:
            raise ValueError("Invalid severity value") from exc

        now = _utc_now()
        icao = (icao_code or self.settings.airport_icao).upper()
        department = assign_department(incident_type, airport_area)

        with _lock:
            incident_id = self._generate_id_locked(now)
            incident = Incident(
                incident_id=incident_id,
                incident_type=incident_type,
                severity=severity_enum,
                airport_area=airport_area,
                assigned_department=department,
                status=IncidentStatus.OPEN,
                created_time=now,
                last_updated=now,
                description=description,
                icao_code=icao,
            )
            self._incidents.insert(0, incident)
            payload = self._to_dict(incident)

        logger.info(
            "Created incident %s → %s (%s)",
            payload["incident_id"],
            department,
            severity_raw,
        )
        return payload

    def update_incident(
        self,
        incident_id: str,
        *,
        status: Optional[str] = None,
        description: Optional[str] = None,
        airport_area: Optional[str] = None,
    ) -> dict:
        if status is None and description is None and airport_area is None:
            raise ValueError("At least one field must be provided for update")

        with _lock:
            incident = self._find_locked(incident_id)
            if incident is None:
                raise KeyError(f"Incident not found: {incident_id}")

            if status is not None:
                status_raw = status.strip()
                if status_raw not in _STATUS_VALUES:
                    raise ValueError(
                        "Status must be one of: Open, Assigned, In Progress, Resolved, Closed"
                    )
                incident.status = IncidentStatus(status_raw)

            if description is not None:
                desc = description.strip()
                if not desc:
                    raise ValueError("Description cannot be empty")
                incident.description = desc

            if airport_area is not None:
                area = airport_area.strip()
                if not area:
                    raise ValueError("Airport Area cannot be empty")
                incident.airport_area = area
                incident.assigned_department = assign_department(
                    incident.incident_type, area
                )

            incident.last_updated = _utc_now()
            payload = self._to_dict(incident)

        logger.info("Updated incident %s", incident_id)
        return payload

    def delete_incident(self, incident_id: str) -> dict:
        with _lock:
            incident = self._find_locked(incident_id)
            if incident is None:
                raise KeyError(f"Incident not found: {incident_id}")
            payload = self._to_dict(incident)
            self._incidents = [i for i in self._incidents if i.incident_id != incident_id]

        logger.info("Deleted incident %s", incident_id)
        return payload

    def _find_locked(self, incident_id: str) -> Optional[Incident]:
        for item in self._incidents:
            if item.incident_id == incident_id:
                return item
        return None

    def _generate_id_locked(self, when: datetime) -> str:
        self._seq += 1
        return f"INC-{when.year}-{self._seq:03d}"

    def _next_sequence_seed(self) -> int:
        max_seq = 0
        for item in self._incidents:
            parts = item.incident_id.rsplit("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_seq = max(max_seq, int(parts[1]))
        return max_seq

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
    """Return process-wide singleton so in-memory mutations persist across requests."""
    global _incident_service
    if _incident_service is None:
        with _lock:
            if _incident_service is None:
                _incident_service = IncidentService()
    return _incident_service
