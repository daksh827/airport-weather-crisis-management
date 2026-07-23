"""Impact Service — AOCC operational impact assessment from live weather/alerts."""

from __future__ import annotations

import logging
from typing import Optional

from backend.alert_engine import compute_operational_impact, select_primary_alert, evaluate_condition_alerts
from backend.config import Settings, get_settings
from backend.services.alert_service import AlertService, get_alert_service
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)


class ImpactService:
    """Derives arrival/departure/runway/ground impact statuses for AOCC."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherService] = None,
        alert_service: Optional[AlertService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.weather_service = weather_service or get_weather_service()
        self.alert_service = alert_service or get_alert_service()

    def get_impact(self, icao_code: Optional[str] = None) -> dict:
        """Assess operational impact using the same live weather as alerts."""
        # Ensure alert state is current (also refreshes notifications/history)
        alert_payload = self.alert_service.evaluate_from_live_weather(icao_code)
        weather = self.weather_service.get_current_weather(icao_code)

        # Rebuild primary from payload for typed impact calc
        alerts = evaluate_condition_alerts(weather)
        primary = select_primary_alert(alerts)
        impact = compute_operational_impact(weather, primary)

        logger.info(
            "Operational impact for %s: %s (alert=%s)",
            weather.icao_code,
            impact.overall_status,
            primary.title,
        )

        data = impact.model_dump()
        data["assessed_at"] = impact.assessed_at.isoformat()
        data["primary_alert"] = alert_payload.get("current")
        data["checklist"] = alert_payload.get("checklist", [])
        data["trends"] = alert_payload.get("trends", {})
        return data


def get_impact_service() -> ImpactService:
    return ImpactService()
