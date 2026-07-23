"""Alert Service — evaluates live weather, tracks history, coordinates notifications."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from backend.alert_engine import (
    SEVERITY_RANK,
    compute_weather_trends,
    evaluate_condition_alerts,
    merge_checklist,
    select_primary_alert,
)
from backend.config import Settings, get_settings
from backend.models import (
    AlertHistoryEntry,
    AlertSeverity,
    AlertStatus,
    WeatherAlert,
    WeatherObservation,
    WeatherTrend,
)
from backend.services.notification_service import NotificationService, get_notification_service
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)

_MAX_HISTORY = 100
_lock = threading.Lock()
_history: list[AlertHistoryEntry] = []
_active_alerts: list[WeatherAlert] = []
_primary_alert: Optional[WeatherAlert] = None
_previous_weather: Optional[WeatherObservation] = None
_last_primary_key: Optional[str] = None


class AlertService:
    """AOCC weather alert orchestration using live weather observations."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherService] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.weather_service = weather_service or get_weather_service()
        self.notification_service = notification_service or get_notification_service()

    def evaluate_from_live_weather(self, icao_code: Optional[str] = None) -> dict:
        """Pull live weather, evaluate alerts, update history/notifications/trends."""
        global _previous_weather, _primary_alert, _active_alerts, _last_primary_key

        weather = self.weather_service.get_current_weather(icao_code)
        with _lock:
            previous = _previous_weather
            alerts = evaluate_condition_alerts(weather)
            primary = select_primary_alert(alerts)
            checklist = merge_checklist(alerts)
            trends = compute_weather_trends(weather, previous)

            self._sync_history_and_notifications(alerts, primary, weather)

            _active_alerts = [a for a in alerts if a.severity != AlertSeverity.NORMAL] or alerts
            _primary_alert = primary
            _previous_weather = weather

            logger.info(
                "Alert engine primary=%s severity=%s icao=%s source=%s",
                primary.title,
                primary.severity.value,
                weather.icao_code,
                weather.source,
            )

            return {
                "current": self._alert_to_dict(primary),
                "active_alerts": [self._alert_to_dict(a) for a in _active_alerts],
                "checklist": checklist,
                "trends": trends.model_dump(),
                "weather_source": weather.source,
                "icao_code": weather.icao_code,
            }

    def get_current(self, icao_code: Optional[str] = None) -> dict:
        """Return current alert package (re-evaluates from live weather)."""
        return self.evaluate_from_live_weather(icao_code)

    def get_history(self, limit: int = 50) -> list[dict]:
        """Return newest-first alert history."""
        with _lock:
            rows = list(_history)[: max(1, min(limit, _MAX_HISTORY))]
        return [row.model_dump() for row in rows]

    def get_trends(self) -> WeatherTrend:
        with _lock:
            if _previous_weather is None or _primary_alert is None:
                return WeatherTrend(
                    temperature="→",
                    wind="→",
                    visibility="Stable",
                    humidity="→",
                    rainfall="→",
                    summary="Awaiting comparative observation.",
                )
            # trends already computed during evaluate; recompute from last pair if needed
            current = self.weather_service.get_current_weather()
            return compute_weather_trends(current, _previous_weather)

    def _sync_history_and_notifications(
        self,
        alerts: list[WeatherAlert],
        primary: WeatherAlert,
        weather: WeatherObservation,
    ) -> None:
        global _last_primary_key, _history

        primary_key = f"{primary.severity.value}:{primary.condition}:{primary.title}"

        # Clear previous non-matching active history rows visually via CLEARED entries
        if _last_primary_key and _last_primary_key != primary_key:
            prev_title = _last_primary_key.split(":", 2)[-1]
            cleared = AlertHistoryEntry(
                id=primary.id + "_clr",
                time=primary.timestamp,
                alert=prev_title,
                severity=AlertSeverity.NORMAL,
                status=AlertStatus.CLEARED,
                weather_condition=weather.weather_description,
                aocc_action="Previous alert cleared / superseded",
            )
            _history.insert(0, cleared)
            self.notification_service.add(
                f"Alert cleared: {prev_title}",
                category="alert",
                severity=AlertSeverity.NORMAL.value,
            )

        if _last_primary_key != primary_key:
            entry = AlertHistoryEntry(
                id=primary.id,
                time=primary.timestamp,
                alert=primary.title,
                severity=primary.severity,
                status=AlertStatus.ACTIVE,
                weather_condition=weather.weather_description,
                aocc_action=primary.recommended_action,
            )
            _history.insert(0, entry)
            _history[:] = _history[:_MAX_HISTORY]

            if primary.severity == AlertSeverity.NORMAL:
                self.notification_service.add(
                    f"Conditions normal — {weather.weather_description}",
                    category="weather",
                    severity=primary.severity.value,
                )
            else:
                self.notification_service.add(
                    f"{primary.title}: {primary.description}",
                    category="alert",
                    severity=primary.severity.value,
                )
                if SEVERITY_RANK[primary.severity] >= SEVERITY_RANK[AlertSeverity.WARNING]:
                    self.notification_service.add(
                        "Operations notified of elevated weather alert",
                        category="ops",
                        severity=primary.severity.value,
                    )

            # Condition-specific feed lines
            if weather.visibility < 3000:
                self.notification_service.add(
                    f"Visibility reduced to {weather.visibility:.0f} m",
                    category="weather",
                    severity=primary.severity.value,
                )

            _last_primary_key = primary_key

    @staticmethod
    def _alert_to_dict(alert: WeatherAlert) -> dict:
        data = alert.model_dump()
        data["severity"] = alert.severity.value
        data["status"] = alert.status.value
        data["timestamp"] = alert.timestamp.isoformat()
        return data


def get_alert_service() -> AlertService:
    return AlertService()
