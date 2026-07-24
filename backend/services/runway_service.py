"""Runway Operations Service — runway status influenced by weather severity."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.severity_service import SeverityService, get_severity_service
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)


class RunwayOperationsService:
    """Derives runway operational status from existing severity assessment."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        severity_service: Optional[SeverityService] = None,
        weather_service: Optional[WeatherService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.severity_service = severity_service or get_severity_service()
        self.weather_service = weather_service or get_weather_service()

    def get_runway_operations(self, icao_code: Optional[str] = None) -> dict:
        """Return primary runway status for AOCC (VIDP 28/10 by default)."""
        weather = self.weather_service.get_current_weather(icao_code)
        assessment = self.severity_service.assess_from_weather(weather)
        level = int(assessment.level.value)

        if level >= 3:
            status = "CLOSED"
            surface = "Standing Water" if weather.rainfall >= 5 else "Wet"
            inspection = "Pending"
            lighting = "Operational"
        elif level == 2:
            status = "LIMITED"
            surface = "Wet" if weather.rainfall > 0 or "rain" in weather.weather_description.lower() else "Dry"
            inspection = "Completed" if weather.visibility >= 1000 else "Pending"
            lighting = "Operational"
        else:
            status = "OPEN"
            surface = "Wet" if weather.rainfall > 0 else "Dry"
            inspection = "Completed"
            lighting = "Operational" if weather.visibility >= 800 else "Maintenance"

        # Prefer runway matching wind when possible (simplified VIDP pair)
        runway_number = "28/10"
        if "W" in (weather.wind_direction or "").upper() or "NW" in (weather.wind_direction or "").upper():
            runway_number = "28/10"
        elif "E" in (weather.wind_direction or "").upper() or "SE" in (weather.wind_direction or "").upper():
            runway_number = "09/27"

        now = datetime.now(timezone.utc)
        payload = {
            "runway_number": runway_number,
            "status": status,
            "surface": surface,
            "inspection": inspection,
            "lighting": lighting,
            "severity_level": level,
            "icao_code": weather.icao_code,
            "last_updated": now.isoformat(),
        }
        logger.info(
            "Runway ops for %s: %s status=%s (severity L%s)",
            payload["icao_code"],
            runway_number,
            status,
            level,
        )
        return payload


def get_runway_operations_service() -> RunwayOperationsService:
    return RunwayOperationsService()
