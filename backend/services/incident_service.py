"""Incident Management Service — Phase 6A–6C (CRUD, timeline, history, export)."""

from __future__ import annotations

import csv
import io
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    TimelineEvent,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_incident_service: Optional["IncidentService"] = None

_CREATE_SEVERITIES = {
    IncidentSeverity.LEVEL_1.value,
    IncidentSeverity.LEVEL_2.value,
    IncidentSeverity.LEVEL_3.value,
}

_STATUS_VALUES = {s.value for s in IncidentStatus}

_SEVERITY_RANK = {
    IncidentSeverity.CRITICAL.value: 5,
    IncidentSeverity.HIGH.value: 4,
    IncidentSeverity.LEVEL_3.value: 4,
    IncidentSeverity.MEDIUM.value: 3,
    IncidentSeverity.LEVEL_2.value: 3,
    IncidentSeverity.LOW.value: 2,
    IncidentSeverity.LEVEL_1.value: 1,
}

_STATUS_RANK = {
    IncidentStatus.OPEN.value: 1,
    IncidentStatus.ASSIGNED.value: 2,
    IncidentStatus.IN_PROGRESS.value: 3,
    IncidentStatus.RESOLVED.value: 4,
    IncidentStatus.CLOSED.value: 5,
}

_HISTORY_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}


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


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class IncidentService:
    """In-memory AOCC incident store with timeline, history, and export."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._incidents = self._build_mock_incidents()
        self._seq = self._next_sequence_seed()

    def list_incidents(
        self,
        icao_code: Optional[str] = None,
        *,
        search: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        department: Optional[str] = None,
        incident_type: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()
        with _lock:
            items = [
                self._to_dict(item)
                for item in self._incidents
                if item.icao_code == icao
            ]

        items = self._apply_filters(
            items,
            search=search,
            severity=severity,
            status=status,
            department=department,
            incident_type=incident_type,
        )
        items = self._apply_sort(items, sort or "newest")
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
                if i.resolved_time
                and i.resolved_time.astimezone(timezone.utc).date() == today
            )
            closed_today = sum(
                1
                for i in scoped
                if i.status == IncidentStatus.CLOSED
                and i.closed_time
                and i.closed_time.astimezone(timezone.utc).date() == today
            )
            # Fallback: resolved status updated today without resolved_time stamp
            if resolved_today == 0:
                resolved_today = sum(
                    1
                    for i in scoped
                    if i.status == IncidentStatus.RESOLVED
                    and i.last_updated.astimezone(timezone.utc).date() == today
                )
            if closed_today == 0:
                closed_today = sum(
                    1
                    for i in scoped
                    if i.status == IncidentStatus.CLOSED
                    and i.last_updated.astimezone(timezone.utc).date() == today
                )

            durations = []
            for item in scoped:
                end = item.resolved_time or (
                    item.closed_time if item.status == IncidentStatus.CLOSED else None
                )
                if end is None:
                    continue
                durations.append((end - item.created_time).total_seconds())

        metrics = self._resolution_metrics(durations)
        data = {
            "open_incidents": open_count,
            "assigned": assigned,
            "in_progress": in_progress,
            "resolved_today": resolved_today,
            "closed_today": closed_today,
            "avg_resolution_time": metrics["average"],
            "fastest_resolution": metrics["fastest"],
            "longest_resolution": metrics["longest"],
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

    def get_history(self, icao_code: Optional[str] = None) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()
        with _lock:
            rows = [
                self._history_row(item)
                for item in self._incidents
                if item.icao_code == icao and item.status in _HISTORY_STATUSES
            ]
        rows.sort(
            key=lambda row: row.get("closed_time")
            or row.get("resolution_time")
            or row.get("created_time")
            or "",
            reverse=True,
        )
        return {"items": rows, "total": len(rows)}

    def get_timeline(self, incident_id: str) -> dict:
        with _lock:
            incident = self._find_locked(incident_id)
            if incident is None:
                raise KeyError(f"Incident not found: {incident_id}")
            events = [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "message": event.message,
                    "event_type": event.event_type,
                }
                for event in sorted(incident.timeline, key=lambda e: e.timestamp)
            ]
            return {
                "incident_id": incident.incident_id,
                "incident_type": incident.incident_type,
                "status": incident.status.value,
                "assigned_department": incident.assigned_department,
                "events": events,
                "total": len(events),
            }

    def export_history_csv(self, icao_code: Optional[str] = None) -> tuple[str, str]:
        """Return (filename, csv_text) for incident history export."""
        icao = (icao_code or self.settings.airport_icao).upper()
        history = self.get_history(icao)
        stamp = _utc_now().strftime("%Y%m%d")
        filename = f"{icao}_Incident_Report_{stamp}.csv"

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Incident ID",
                "Incident Type",
                "Resolution Time",
                "Closed Time",
                "Department",
                "Final Status",
                "Severity",
                "Airport Area",
                "Created Time",
                "Description",
            ]
        )
        for row in history["items"]:
            writer.writerow(
                [
                    row.get("incident_id", ""),
                    row.get("incident_type", ""),
                    row.get("resolution_time") or "",
                    row.get("closed_time") or "",
                    row.get("assigned_department", ""),
                    row.get("final_status", ""),
                    row.get("severity", ""),
                    row.get("airport_area", ""),
                    row.get("created_time", ""),
                    row.get("description") or "",
                ]
            )
        return filename, buffer.getvalue()

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
                timeline=[
                    TimelineEvent(
                        timestamp=now,
                        message="Incident Created",
                        event_type="created",
                    ),
                    TimelineEvent(
                        timestamp=now + timedelta(milliseconds=1),
                        message=f"Assigned to {department}",
                        event_type="assigned",
                    ),
                ],
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

            now = _utc_now()

            if status is not None:
                status_raw = status.strip()
                if status_raw not in _STATUS_VALUES:
                    raise ValueError(
                        "Status must be one of: Open, Assigned, In Progress, Resolved, Closed"
                    )
                new_status = IncidentStatus(status_raw)
                if new_status != incident.status:
                    self._append_status_timeline(incident, new_status, now)
                    incident.status = new_status
                    if new_status == IncidentStatus.RESOLVED and incident.resolved_time is None:
                        incident.resolved_time = now
                    if new_status == IncidentStatus.CLOSED:
                        if incident.resolved_time is None:
                            incident.resolved_time = now
                        incident.closed_time = now

            if description is not None:
                desc = description.strip()
                if not desc:
                    raise ValueError("Description cannot be empty")
                if desc != (incident.description or ""):
                    incident.description = desc
                    incident.timeline.append(
                        TimelineEvent(
                            timestamp=now,
                            message="Description updated",
                            event_type="updated",
                        )
                    )

            if airport_area is not None:
                area = airport_area.strip()
                if not area:
                    raise ValueError("Airport Area cannot be empty")
                if area != incident.airport_area:
                    incident.airport_area = area
                    new_dept = assign_department(incident.incident_type, area)
                    prev_dept = incident.assigned_department
                    incident.assigned_department = new_dept
                    incident.timeline.append(
                        TimelineEvent(
                            timestamp=now,
                            message=f"Airport area updated to {area}",
                            event_type="updated",
                        )
                    )
                    if new_dept != prev_dept:
                        incident.timeline.append(
                            TimelineEvent(
                                timestamp=now + timedelta(milliseconds=1),
                                message=f"Assigned to {new_dept}",
                                event_type="assigned",
                            )
                        )

            incident.last_updated = now
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

    @staticmethod
    def _append_status_timeline(
        incident: Incident, new_status: IncidentStatus, when: datetime
    ) -> None:
        if new_status == IncidentStatus.ASSIGNED:
            incident.timeline.append(
                TimelineEvent(
                    timestamp=when,
                    message=f"Assigned to {incident.assigned_department}",
                    event_type="assigned",
                )
            )
        elif new_status == IncidentStatus.CLOSED:
            incident.timeline.append(
                TimelineEvent(
                    timestamp=when,
                    message="Incident Closed",
                    event_type="closed",
                )
            )
        else:
            incident.timeline.append(
                TimelineEvent(
                    timestamp=when,
                    message=f"Status changed to {new_status.value}",
                    event_type="status_changed",
                )
            )

    @staticmethod
    def _resolution_metrics(durations: list[float]) -> dict:
        if not durations:
            return {"average": "—", "fastest": "—", "longest": "—"}
        return {
            "average": _format_duration(sum(durations) / len(durations)),
            "fastest": _format_duration(min(durations)),
            "longest": _format_duration(max(durations)),
        }

    @staticmethod
    def _apply_filters(
        items: list[dict],
        *,
        search: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        department: Optional[str] = None,
        incident_type: Optional[str] = None,
    ) -> list[dict]:
        result = items
        if severity:
            sev = severity.strip().lower()
            result = [i for i in result if str(i.get("severity", "")).lower() == sev]
        if status:
            st = status.strip().lower()
            result = [i for i in result if str(i.get("status", "")).lower() == st]
        if department:
            dept = department.strip().lower()
            result = [
                i
                for i in result
                if str(i.get("assigned_department", "")).lower() == dept
            ]
        if incident_type:
            itype = incident_type.strip().lower()
            result = [
                i for i in result if str(i.get("incident_type", "")).lower() == itype
            ]
        if search:
            q = search.strip().lower()
            if q:
                result = [
                    i
                    for i in result
                    if q
                    in " ".join(
                        [
                            str(i.get("incident_id", "")),
                            str(i.get("incident_type", "")),
                            str(i.get("airport_area", "")),
                            str(i.get("assigned_department", "")),
                            str(i.get("description") or ""),
                        ]
                    ).lower()
                ]
        return result

    @staticmethod
    def _apply_sort(items: list[dict], sort: str) -> list[dict]:
        key = (sort or "newest").strip().lower().replace(" ", "_")
        if key in {"oldest", "oldest_first"}:
            return sorted(items, key=lambda r: r.get("created_time") or "")
        if key in {"highest_severity", "severity_desc"}:
            return sorted(
                items,
                key=lambda r: (
                    _SEVERITY_RANK.get(str(r.get("severity")), 0),
                    r.get("created_time") or "",
                ),
                reverse=True,
            )
        if key in {"lowest_severity", "severity_asc"}:
            return sorted(
                items,
                key=lambda r: (
                    _SEVERITY_RANK.get(str(r.get("severity")), 0),
                    r.get("created_time") or "",
                ),
            )
        if key == "status":
            return sorted(
                items,
                key=lambda r: (
                    _STATUS_RANK.get(str(r.get("status")), 99),
                    r.get("created_time") or "",
                ),
            )
        if key in {"created_time", "created"}:
            return sorted(
                items, key=lambda r: r.get("created_time") or "", reverse=True
            )
        # newest / newest_first default
        return sorted(items, key=lambda r: r.get("created_time") or "", reverse=True)

    def _history_row(self, incident: Incident) -> dict:
        return {
            "incident_id": incident.incident_id,
            "incident_type": incident.incident_type,
            "resolution_time": (
                incident.resolved_time.isoformat() if incident.resolved_time else None
            ),
            "closed_time": (
                incident.closed_time.isoformat() if incident.closed_time else None
            ),
            "assigned_department": incident.assigned_department,
            "final_status": incident.status.value,
            "severity": incident.severity.value,
            "airport_area": incident.airport_area,
            "created_time": incident.created_time.isoformat(),
            "description": incident.description,
            "icao_code": incident.icao_code,
        }

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

        inc1_created = now - timedelta(hours=2, minutes=15)
        inc2_created = now - timedelta(hours=1, minutes=40)
        inc3_created = now - timedelta(minutes=55)
        inc4_created = now - timedelta(hours=5)
        inc4_resolved = now - timedelta(hours=1)

        return [
            Incident(
                incident_id="INC-2026-001",
                incident_type="Low Visibility",
                severity=IncidentSeverity.HIGH,
                airport_area="Runway 09/27",
                assigned_department="ATC",
                status=IncidentStatus.IN_PROGRESS,
                created_time=inc1_created,
                last_updated=now - timedelta(minutes=18),
                description="Reduced visibility impacting arrival acceptance rate.",
                icao_code=icao,
                timeline=[
                    TimelineEvent(
                        timestamp=inc1_created,
                        message="Incident Created",
                        event_type="created",
                    ),
                    TimelineEvent(
                        timestamp=inc1_created + timedelta(minutes=3),
                        message="Assigned to ATC",
                        event_type="assigned",
                    ),
                    TimelineEvent(
                        timestamp=inc1_created + timedelta(minutes=9),
                        message="Status changed to In Progress",
                        event_type="status_changed",
                    ),
                ],
            ),
            Incident(
                incident_id="INC-2026-002",
                incident_type="Ground Equipment Shortage",
                severity=IncidentSeverity.MEDIUM,
                airport_area="Apron / Terminal 3",
                assigned_department="Ground Ops",
                status=IncidentStatus.ASSIGNED,
                created_time=inc2_created,
                last_updated=now - timedelta(minutes=35),
                description="Pushback and fuel truck availability constrained.",
                icao_code=icao,
                timeline=[
                    TimelineEvent(
                        timestamp=inc2_created,
                        message="Incident Created",
                        event_type="created",
                    ),
                    TimelineEvent(
                        timestamp=inc2_created + timedelta(minutes=5),
                        message="Assigned to Ground Ops",
                        event_type="assigned",
                    ),
                ],
            ),
            Incident(
                incident_id="INC-2026-003",
                incident_type="Passenger Congestion",
                severity=IncidentSeverity.MEDIUM,
                airport_area="Terminal 2 Security",
                assigned_department="Terminal",
                status=IncidentStatus.OPEN,
                created_time=inc3_created,
                last_updated=inc3_created,
                description="Security queue elevated due to weather delays.",
                icao_code=icao,
                timeline=[
                    TimelineEvent(
                        timestamp=inc3_created,
                        message="Incident Created",
                        event_type="created",
                    ),
                    TimelineEvent(
                        timestamp=inc3_created + timedelta(seconds=1),
                        message="Assigned to Terminal",
                        event_type="assigned",
                    ),
                ],
            ),
            Incident(
                incident_id="INC-2026-004",
                incident_type="Weather Watch",
                severity=IncidentSeverity.LOW,
                airport_area="Airport-wide",
                assigned_department="AOCC",
                status=IncidentStatus.RESOLVED,
                created_time=inc4_created,
                last_updated=inc4_resolved,
                resolved_time=inc4_resolved,
                description="Fog watch monitored and cleared for morning bank.",
                icao_code=icao,
                timeline=[
                    TimelineEvent(
                        timestamp=inc4_created,
                        message="Incident Created",
                        event_type="created",
                    ),
                    TimelineEvent(
                        timestamp=inc4_created + timedelta(minutes=4),
                        message="Assigned to AOCC",
                        event_type="assigned",
                    ),
                    TimelineEvent(
                        timestamp=inc4_created + timedelta(minutes=40),
                        message="Status changed to In Progress",
                        event_type="status_changed",
                    ),
                    TimelineEvent(
                        timestamp=inc4_resolved,
                        message="Status changed to Resolved",
                        event_type="status_changed",
                    ),
                ],
            ),
        ]

    @staticmethod
    def _to_dict(incident: Incident) -> dict:
        payload = incident.model_dump()
        payload["severity"] = incident.severity.value
        payload["status"] = incident.status.value
        payload["created_time"] = incident.created_time.isoformat()
        payload["last_updated"] = incident.last_updated.isoformat()
        payload["resolved_time"] = (
            incident.resolved_time.isoformat() if incident.resolved_time else None
        )
        payload["closed_time"] = (
            incident.closed_time.isoformat() if incident.closed_time else None
        )
        payload["timeline"] = [
            {
                "timestamp": event.timestamp.isoformat(),
                "message": event.message,
                "event_type": event.event_type,
            }
            for event in incident.timeline
        ]
        return payload


def get_incident_service() -> IncidentService:
    """Return process-wide singleton so in-memory mutations persist across requests."""
    global _incident_service
    if _incident_service is None:
        with _lock:
            if _incident_service is None:
                _incident_service = IncidentService()
    return _incident_service
