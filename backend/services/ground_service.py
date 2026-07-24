"""Ground Operations Service — simulated airside vehicle fleets."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.severity_service import SeverityService, get_severity_service

logger = logging.getLogger(__name__)

_FLEET_KEYS = (
    "fuel_trucks",
    "baggage_vehicles",
    "pushback_vehicles",
    "catering_vehicles",
    "maintenance_vehicles",
    "follow_me_vehicles",
)

# available / in_use / maintenance by severity
_FLEET_BASELINES = {
    1: {
        "fuel_trucks": {"available": 12, "in_use": 8, "maintenance": 2},
        "baggage_vehicles": {"available": 34, "in_use": 22, "maintenance": 4},
        "pushback_vehicles": {"available": 10, "in_use": 6, "maintenance": 1},
        "catering_vehicles": {"available": 14, "in_use": 9, "maintenance": 2},
        "maintenance_vehicles": {"available": 8, "in_use": 3, "maintenance": 1},
        "follow_me_vehicles": {"available": 6, "in_use": 2, "maintenance": 0},
    },
    2: {
        "fuel_trucks": {"available": 7, "in_use": 12, "maintenance": 3},
        "baggage_vehicles": {"available": 18, "in_use": 36, "maintenance": 6},
        "pushback_vehicles": {"available": 5, "in_use": 10, "maintenance": 2},
        "catering_vehicles": {"available": 8, "in_use": 14, "maintenance": 3},
        "maintenance_vehicles": {"available": 4, "in_use": 7, "maintenance": 2},
        "follow_me_vehicles": {"available": 3, "in_use": 5, "maintenance": 1},
    },
    3: {
        "fuel_trucks": {"available": 3, "in_use": 14, "maintenance": 5},
        "baggage_vehicles": {"available": 8, "in_use": 42, "maintenance": 10},
        "pushback_vehicles": {"available": 2, "in_use": 11, "maintenance": 4},
        "catering_vehicles": {"available": 3, "in_use": 16, "maintenance": 5},
        "maintenance_vehicles": {"available": 2, "in_use": 9, "maintenance": 3},
        "follow_me_vehicles": {"available": 1, "in_use": 6, "maintenance": 2},
    },
}


class GroundOperationsService:
    """Simulated ground support equipment availability by severity."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        severity_service: Optional[SeverityService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.severity_service = severity_service or get_severity_service()

    def get_ground_operations(self, icao_code: Optional[str] = None) -> dict:
        assessment = self.severity_service.assess_current(icao_code)
        level = int(assessment.level.value)
        profile = _FLEET_BASELINES.get(level, _FLEET_BASELINES[1])

        fleet = {key: dict(profile[key]) for key in _FLEET_KEYS}
        total_available = sum(v["available"] for v in fleet.values())
        total_units = sum(v["available"] + v["in_use"] + v["maintenance"] for v in fleet.values())
        availability_pct = round((total_available / total_units) * 100, 1) if total_units else 0.0

        status = "NORMAL"
        if level == 2:
            status = "CONSTRAINED"
        elif level >= 3:
            status = "RESTRICTED"

        data = {
            **fleet,
            "ground_status": status,
            "fleet_availability_pct": availability_pct,
            "severity_level": level,
            "icao_code": (icao_code or self.settings.airport_icao).upper(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Ground ops for %s (severity L%s): status=%s availability=%s%%",
            data["icao_code"],
            level,
            status,
            availability_pct,
        )
        return data


def get_ground_operations_service() -> GroundOperationsService:
    return GroundOperationsService()
