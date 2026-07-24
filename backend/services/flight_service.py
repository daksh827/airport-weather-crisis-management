"""Flight Operations Service — simulated daily AOCC flight statistics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.severity_service import SeverityService, get_severity_service

logger = logging.getLogger(__name__)

# Baseline VIDP daily ops profile (simulated, deterministic by severity band)
_BASELINE = {
    1: {"arrivals": 412, "departures": 418, "delayed": 14, "cancelled": 2, "diverted": 0},
    2: {"arrivals": 388, "departures": 394, "delayed": 47, "cancelled": 9, "diverted": 3},
    3: {"arrivals": 296, "departures": 301, "delayed": 112, "cancelled": 28, "diverted": 11},
}


class FlightOperationsService:
    """Provides realistic simulated flight operations counts for the AOCC dashboard."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        severity_service: Optional[SeverityService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.severity_service = severity_service or get_severity_service()

    def get_flight_operations(self, icao_code: Optional[str] = None) -> dict:
        """Return today's simulated flight operations summary."""
        assessment = self.severity_service.assess_current(icao_code)
        level = int(assessment.level.value)
        profile = dict(_BASELINE.get(level, _BASELINE[1]))

        # Light time-of-day variation so successive polls look live without randomness spikes
        hour = datetime.now(timezone.utc).hour
        drift = (hour % 5) - 2
        profile["arrivals"] = max(0, profile["arrivals"] + drift)
        profile["departures"] = max(0, profile["departures"] + drift)
        if level >= 2:
            profile["delayed"] = max(0, profile["delayed"] + abs(drift))

        now = datetime.now(timezone.utc)
        payload = {
            "arrivals": profile["arrivals"],
            "departures": profile["departures"],
            "delayed": profile["delayed"],
            "cancelled": profile["cancelled"],
            "diverted": profile["diverted"],
            "last_updated": now.isoformat(),
            "icao_code": (icao_code or self.settings.airport_icao).upper(),
            "severity_level": level,
        }
        logger.info(
            "Flight ops summary for %s (severity L%s): A=%s D=%s delayed=%s",
            payload["icao_code"],
            level,
            payload["arrivals"],
            payload["departures"],
            payload["delayed"],
        )
        return payload


def get_flight_operations_service() -> FlightOperationsService:
    return FlightOperationsService()
