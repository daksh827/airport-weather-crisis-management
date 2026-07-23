"""Severity service — evaluates operational crisis level from weather."""

from __future__ import annotations

import logging
from typing import Optional

from backend.config import Settings, get_settings
from backend.models import SeverityAssessment, WeatherObservation
from backend.severity import assess_severity
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)


class SeverityService:
    """Application service for airport operational severity assessment."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.weather_service = weather_service or get_weather_service()

    def assess_current(self, icao_code: Optional[str] = None) -> SeverityAssessment:
        """Pull current weather and classify severity."""
        weather = self.weather_service.get_current_weather(icao_code)
        return self.assess_from_weather(weather)

    def assess_from_weather(self, weather: WeatherObservation) -> SeverityAssessment:
        """Classify severity from an existing weather observation."""
        assessment = assess_severity(weather)
        logger.info(
            "Severity service result for %s: Level %s",
            weather.icao_code,
            assessment.level.value,
        )
        return assessment


def get_severity_service() -> SeverityService:
    """FastAPI dependency factory for SeverityService."""
    return SeverityService()
