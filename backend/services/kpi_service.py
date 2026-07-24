"""Airport KPI Service — aggregates ops metrics influenced by weather severity."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.flight_service import FlightOperationsService, get_flight_operations_service
from backend.services.ground_service import GroundOperationsService, get_ground_operations_service
from backend.services.runway_service import RunwayOperationsService, get_runway_operations_service
from backend.services.severity_service import SeverityService, get_severity_service
from backend.services.terminal_service import TerminalOperationsService, get_terminal_operations_service

logger = logging.getLogger(__name__)

_EFFICIENCY = {1: 98, 2: 93, 3: 82}
_AVG_DELAY_MIN = {1: 8, 2: 22, 3: 47}
_PASSENGERS = {1: 118400, 2: 109200, 3: 86400}

_AIRPORT_STATUS = {
    1: "Operational",
    2: "Heightened Watch",
    3: "Limited Operations",
}

_AIRPORT_STATUS_COLOR = {
    "Operational": "#22c55e",
    "Heightened Watch": "#eab308",
    "Limited Operations": "#f97316",
    "Disrupted": "#ef4444",
    "Closed": "#b91c1c",
}


class AirportKPIService:
    """Builds Airport KPI dashboard payload from existing ops services."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        severity_service: Optional[SeverityService] = None,
        flight_service: Optional[FlightOperationsService] = None,
        runway_service: Optional[RunwayOperationsService] = None,
        terminal_service: Optional[TerminalOperationsService] = None,
        ground_service: Optional[GroundOperationsService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.severity_service = severity_service or get_severity_service()
        self.flight_service = flight_service or get_flight_operations_service()
        self.runway_service = runway_service or get_runway_operations_service()
        self.terminal_service = terminal_service or get_terminal_operations_service()
        self.ground_service = ground_service or get_ground_operations_service()

    def get_kpis(self, icao_code: Optional[str] = None) -> dict:
        assessment = self.severity_service.assess_current(icao_code)
        level = int(assessment.level.value)

        flights = self.flight_service.get_flight_operations(icao_code)
        runway = self.runway_service.get_runway_operations(icao_code)
        terminals = self.terminal_service.get_terminal_operations(icao_code)
        ground = self.ground_service.get_ground_operations(icao_code)

        efficiency = _EFFICIENCY.get(level, 98)
        airport_status = _AIRPORT_STATUS.get(level, "Operational")

        # Escalate to Disrupted/Closed only for extreme Level 3 + closed runway
        if level >= 3 and runway.get("status") == "CLOSED":
            airport_status = "Disrupted"
            efficiency = min(efficiency, 78)

        flights_today = int(flights["arrivals"]) + int(flights["departures"])
        terminal_utilization = self._terminal_utilization(terminals)
        runway_availability = self._runway_availability(runway.get("status", "OPEN"))

        data = {
            "flights_today": flights_today,
            "passengers_today": _PASSENGERS.get(level, 118400),
            "delayed_flights": flights["delayed"],
            "cancelled_flights": flights["cancelled"],
            "average_delay": _AVG_DELAY_MIN.get(level, 8),
            "runway_availability": runway_availability,
            "terminal_utilization": terminal_utilization,
            "ground_vehicle_availability": ground.get("fleet_availability_pct", 0),
            "operational_efficiency": efficiency,
            "airport_status": airport_status,
            "airport_status_color": _AIRPORT_STATUS_COLOR.get(airport_status, "#22c55e"),
            "severity_level": level,
            "icao_code": (icao_code or self.settings.airport_icao).upper(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Airport KPIs for %s (L%s): efficiency=%s%% status=%s",
            data["icao_code"],
            level,
            efficiency,
            airport_status,
        )
        return data

    @staticmethod
    def _terminal_utilization(terminals: dict) -> float:
        occupied = 0
        total = 0
        for key in ("terminal1", "terminal2", "terminal3"):
            block = terminals.get(key) or {}
            occ = int(block.get("occupied_gates", 0))
            avail = int(block.get("available_gates", 0))
            occupied += occ
            total += occ + avail
        if total <= 0:
            return 0.0
        return round((occupied / total) * 100, 1)

    @staticmethod
    def _runway_availability(status: str) -> float:
        mapping = {"OPEN": 100.0, "LIMITED": 65.0, "CLOSED": 0.0}
        return mapping.get(str(status).upper(), 100.0)


def get_airport_kpi_service() -> AirportKPIService:
    return AirportKPIService()
