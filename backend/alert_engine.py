"""Weather Alert Engine — evaluates live observations into AOCC alerts.

Produces NORMAL / WATCH / WARNING / CRITICAL bands with operational guidance.
Uses live WeatherObservation values (Tomorrow.io or mock failover).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.models import (
    AlertSeverity,
    AlertStatus,
    OperationalImpact,
    WeatherAlert,
    WeatherObservation,
    WeatherTrend,
)

logger = logging.getLogger(__name__)

SEVERITY_RANK = {
    AlertSeverity.NORMAL: 0,
    AlertSeverity.WATCH: 1,
    AlertSeverity.WARNING: 2,
    AlertSeverity.CRITICAL: 3,
}

SEVERITY_META: dict[AlertSeverity, dict[str, str]] = {
    AlertSeverity.NORMAL: {"color": "#22c55e", "icon": "normal", "label": "Normal"},
    AlertSeverity.WATCH: {"color": "#eab308", "icon": "watch", "label": "Watch"},
    AlertSeverity.WARNING: {"color": "#f97316", "icon": "warning", "label": "Warning"},
    AlertSeverity.CRITICAL: {"color": "#ef4444", "icon": "critical", "label": "Critical"},
}

# Thresholds aligned with AOCC ops (VIDP-oriented)
VIS_CRITICAL_M = 550
VIS_WARNING_M = 1200
VIS_WATCH_M = 3000
WIND_CRITICAL_KT = 40
WIND_WARNING_KT = 28
WIND_WATCH_KT = 18
RAIN_CRITICAL_MM = 25
RAIN_WARNING_MM = 10
RAIN_WATCH_MM = 3
TEMP_HEAT_CRITICAL_C = 45
TEMP_HEAT_WARNING_C = 40
TEMP_HEAT_WATCH_C = 36
HUMIDITY_WATCH_PCT = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _desc_tokens(weather: WeatherObservation) -> str:
    return (weather.weather_description or "").lower()


def evaluate_condition_alerts(weather: WeatherObservation) -> list[WeatherAlert]:
    """Evaluate all monitored conditions and return candidate alerts."""
    now = _now()
    text = _desc_tokens(weather)
    alerts: list[WeatherAlert] = []

    # Visibility / Fog
    foggy = any(t in text for t in ("fog", "mist", "haze"))
    if weather.visibility <= VIS_CRITICAL_M or (foggy and weather.visibility <= VIS_CRITICAL_M):
        title = "Fog Critical" if foggy else "Low Visibility Critical"
        alerts.append(
            _build_alert(
                title=title,
                description=(
                    f"Visibility is {weather.visibility:.0f} m"
                    f"{' with fog/mist reported' if foggy else ''}. "
                    "Expect LVP activation and significant capacity loss."
                ),
                severity=AlertSeverity.CRITICAL,
                condition="Fog" if foggy else "Visibility",
                affected=["Arrival Operations", "Departure Operations", "Runway Operations", "Taxiway Visibility"],
                action="Activate Low Visibility Procedures and coordinate arrival metering with ATC.",
                checklist=[
                    "Notify ATC",
                    "Prepare Low Visibility Procedures",
                    "Inform Airlines",
                    "Increase Airfield Inspection",
                    "Prepare Diversion Procedures",
                ],
                weather=weather,
                now=now,
            )
        )
    elif weather.visibility <= VIS_WARNING_M or (foggy and weather.visibility <= VIS_WARNING_M):
        title = "Fog Warning" if foggy else "Reduced Visibility Warning"
        alerts.append(
            _build_alert(
                title=title,
                description=(
                    f"Visibility is {weather.visibility:.0f} m"
                    f"{' — fog/mist present' if foggy else ''}. "
                    "Arrival/departure rates may be reduced."
                ),
                severity=AlertSeverity.WARNING,
                condition="Fog" if foggy else "Visibility",
                affected=["Arrival Operations", "Departure Operations", "Taxiway Visibility"],
                action="Stand up LVP readiness and brief airlines on possible delays.",
                checklist=[
                    "Notify ATC",
                    "Inform Airlines",
                    "Prepare Low Visibility Procedures",
                    "Increase Airfield Inspection",
                ],
                weather=weather,
                now=now,
            )
        )
    elif weather.visibility <= VIS_WATCH_M or foggy:
        title = "Fog Watch" if foggy else "Visibility Watch"
        alerts.append(
            _build_alert(
                title=title,
                description=(
                    f"Visibility {weather.visibility:.0f} m"
                    f"{' with fog/mist reported' if foggy else ''}. "
                    "Monitor for further deterioration."
                ),
                severity=AlertSeverity.WATCH,
                condition="Fog" if foggy else "Visibility",
                affected=["Arrival Operations", "Taxiway Visibility"],
                action="Heighten weather watch and review LVP standby posture.",
                checklist=["Monitor Wind Conditions", "Increase Airfield Inspection", "Notify ATC"],
                weather=weather,
                now=now,
            )
        )

    # Wind
    if weather.wind_speed >= WIND_CRITICAL_KT or "gale" in text:
        alerts.append(
            _build_alert(
                title="Strong Wind Critical",
                description=(
                    f"Wind speed {weather.wind_speed:.1f} kt from {weather.wind_direction}. "
                    "Crosswind / gust limits may be exceeded."
                ),
                severity=AlertSeverity.CRITICAL,
                condition="Strong Wind",
                affected=["Arrival Operations", "Departure Operations", "Runway Operations", "Ground Handling"],
                action="Restrict vulnerable aircraft types and secure ground equipment.",
                checklist=[
                    "Notify ATC",
                    "Inform Airlines",
                    "Monitor Wind Conditions",
                    "Prepare Diversion Procedures",
                    "Increase Airfield Inspection",
                ],
                weather=weather,
                now=now,
            )
        )
    elif weather.wind_speed >= WIND_WARNING_KT:
        alerts.append(
            _build_alert(
                title="Strong Wind Warning",
                description=(
                    f"Wind speed {weather.wind_speed:.1f} kt from {weather.wind_direction}. "
                    "Expect possible go-arounds and ground handling delays."
                ),
                severity=AlertSeverity.WARNING,
                condition="Strong Wind",
                affected=["Arrival Operations", "Departure Operations", "Ground Handling"],
                action="Coordinate runway-in-use and brief ground handlers on wind hazards.",
                checklist=["Notify ATC", "Inform Airlines", "Monitor Wind Conditions"],
                weather=weather,
                now=now,
            )
        )
    elif weather.wind_speed >= WIND_WATCH_KT:
        alerts.append(
            _build_alert(
                title="Wind Watch",
                description=f"Elevated wind {weather.wind_speed:.1f} kt. Continue trend monitoring.",
                severity=AlertSeverity.WATCH,
                condition="Strong Wind",
                affected=["Runway Operations", "Ground Handling"],
                action="Monitor wind trends and apron equipment security.",
                checklist=["Monitor Wind Conditions", "Increase Airfield Inspection"],
                weather=weather,
                now=now,
            )
        )

    # Rain / Thunderstorm
    stormy = any(t in text for t in ("thunder", "storm", "lightning"))
    heavy_rain = weather.rainfall >= RAIN_WARNING_MM or any(
        t in text for t in ("heavy rain", "downpour")
    )
    if stormy:
        severity = (
            AlertSeverity.CRITICAL
            if weather.rainfall >= RAIN_CRITICAL_MM or weather.visibility <= VIS_WARNING_M
            else AlertSeverity.WARNING
        )
        alerts.append(
            _build_alert(
                title="Thunderstorm Critical" if severity == AlertSeverity.CRITICAL else "Thunderstorm Warning",
                description=(
                    f"Thunderstorm conditions reported ({weather.weather_description}). "
                    f"Rainfall intensity {weather.rainfall:.1f} mm."
                ),
                severity=severity,
                condition="Thunderstorm",
                affected=[
                    "Arrival Operations",
                    "Departure Operations",
                    "Runway Operations",
                    "Ground Handling",
                    "Passenger Processing",
                ],
                action="Suspend exposed ramp work and prepare holding/diversion options.",
                checklist=[
                    "Notify ATC",
                    "Inform Airlines",
                    "Prepare Diversion Procedures",
                    "Increase Airfield Inspection",
                    "Monitor Wind Conditions",
                ],
                weather=weather,
                now=now,
            )
        )
    elif weather.rainfall >= RAIN_CRITICAL_MM or (heavy_rain and weather.rainfall >= RAIN_WARNING_MM):
        alerts.append(
            _build_alert(
                title="Heavy Rain Critical" if weather.rainfall >= RAIN_CRITICAL_MM else "Heavy Rain Warning",
                description=(
                    f"Heavy precipitation {weather.rainfall:.1f} mm — "
                    f"{weather.weather_description}. Runway contamination risk elevated."
                ),
                severity=(
                    AlertSeverity.CRITICAL
                    if weather.rainfall >= RAIN_CRITICAL_MM
                    else AlertSeverity.WARNING
                ),
                condition="Heavy Rain",
                affected=["Runway Operations", "Arrival Operations", "Departure Operations", "Ground Handling"],
                action="Increase runway friction checks and review arrival spacing.",
                checklist=[
                    "Increase Airfield Inspection",
                    "Notify ATC",
                    "Inform Airlines",
                    "Prepare Diversion Procedures",
                ],
                weather=weather,
                now=now,
            )
        )
    elif weather.rainfall >= RAIN_WATCH_MM or "rain" in text:
        alerts.append(
            _build_alert(
                title="Rain Watch",
                description=(
                    f"Rainfall {weather.rainfall:.1f} mm ({weather.weather_description}). "
                    "Monitor runway surface conditions."
                ),
                severity=AlertSeverity.WATCH,
                condition="Heavy Rain",
                affected=["Runway Operations", "Ground Handling"],
                action="Increase surface inspection cadence.",
                checklist=["Increase Airfield Inspection", "Monitor Wind Conditions"],
                weather=weather,
                now=now,
            )
        )

    # Heat
    if weather.temperature >= TEMP_HEAT_CRITICAL_C:
        heat_sev = AlertSeverity.CRITICAL
    elif weather.temperature >= TEMP_HEAT_WARNING_C:
        heat_sev = AlertSeverity.WARNING
    elif weather.temperature >= TEMP_HEAT_WATCH_C:
        heat_sev = AlertSeverity.WATCH
    else:
        heat_sev = None

    if heat_sev is not None:
        alerts.append(
            _build_alert(
                title=f"Heat {SEVERITY_META[heat_sev]['label']}",
                description=(
                    f"Temperature {weather.temperature:.1f}°C with humidity "
                    f"{weather.humidity:.0f}%. Expect payload and ground-staff impacts."
                ),
                severity=heat_sev,
                condition="Heat",
                affected=["Ground Handling", "Passenger Processing", "Departure Operations"],
                action="Implement heat-stress protocols for ramp staff and review takeoff performance.",
                checklist=["Inform Airlines", "Notify ATC", "Increase Airfield Inspection"],
                weather=weather,
                now=now,
            )
        )

    # Humidity (watch only unless combined elsewhere)
    if weather.humidity >= HUMIDITY_WATCH_PCT and not foggy:
        alerts.append(
            _build_alert(
                title="Humidity Watch",
                description=(
                    f"Humidity {weather.humidity:.0f}% may contribute to reduced visibility "
                    "or fog formation."
                ),
                severity=AlertSeverity.WATCH,
                condition="Humidity",
                affected=["Taxiway Visibility", "Arrival Operations"],
                action="Monitor visibility trends for fog onset.",
                checklist=["Monitor Wind Conditions", "Prepare Low Visibility Procedures"],
                weather=weather,
                now=now,
            )
        )

    if not alerts:
        alerts.append(
            _build_alert(
                title="Normal Operations",
                description=(
                    f"Conditions within normal parameters: {weather.weather_description}, "
                    f"vis {weather.visibility:.0f} m, wind {weather.wind_speed:.1f} kt."
                ),
                severity=AlertSeverity.NORMAL,
                condition="Normal",
                affected=[],
                action="Maintain standard AOCC monitoring cadence.",
                checklist=["Monitor Wind Conditions", "Increase Airfield Inspection"],
                weather=weather,
                now=now,
            )
        )

    return alerts


def select_primary_alert(alerts: list[WeatherAlert]) -> WeatherAlert:
    """Choose the highest-severity active alert as the current banner alert."""
    ranked = sorted(
        alerts,
        key=lambda a: (SEVERITY_RANK[a.severity], a.timestamp),
        reverse=True,
    )
    return ranked[0]


def merge_checklist(alerts: list[WeatherAlert]) -> list[str]:
    """Deduplicate checklist actions from all active non-NORMAL alerts."""
    items: list[str] = []
    seen: set[str] = set()
    ordered = sorted(alerts, key=lambda a: SEVERITY_RANK[a.severity], reverse=True)
    for alert in ordered:
        if alert.severity == AlertSeverity.NORMAL:
            continue
        for item in alert.checklist:
            if item not in seen:
                seen.add(item)
                items.append(item)
    if not items:
        items = ["Monitor Wind Conditions", "Maintain standard AOCC watch"]
    return items


def compute_operational_impact(
    weather: WeatherObservation,
    primary: WeatherAlert,
) -> OperationalImpact:
    """Map alert severity + weather into AOCC operational impact statuses."""
    sev = primary.severity
    now = _now()

    if sev == AlertSeverity.CRITICAL:
        arrival = departure = "SEVERELY REDUCED"
        runway_ops = "TEMPORARILY RESTRICTED"
        taxi = "POOR"
        ground = "RESTRICTED"
        pax = "DISRUPTED"
        arrival_rate = "SEVERELY REDUCED"
        runway_status = "TEMPORARILY RESTRICTED"
        overall = "CRITICAL IMPACT"
    elif sev == AlertSeverity.WARNING:
        arrival = departure = "REDUCED"
        runway_ops = "LIMITED"
        taxi = "REDUCED"
        ground = "CAUTION"
        pax = "DELAYED"
        arrival_rate = "REDUCED"
        runway_status = "LIMITED"
        overall = "DEGRADED OPERATIONS"
    elif sev == AlertSeverity.WATCH:
        arrival = departure = "MONITOR"
        runway_ops = "OPEN"
        taxi = "MONITOR"
        ground = "NORMAL"
        pax = "NORMAL"
        arrival_rate = "NORMAL"
        runway_status = "OPEN"
        overall = "HEIGHTENED WATCH"
    else:
        arrival = departure = "NORMAL"
        runway_ops = "OPEN"
        taxi = "NORMAL"
        ground = "NORMAL"
        pax = "NORMAL"
        arrival_rate = "NORMAL"
        runway_status = "OPEN"
        overall = "NORMAL OPERATIONS"

    # Refine with specific conditions
    if weather.visibility <= VIS_WARNING_M:
        taxi = "POOR" if weather.visibility <= VIS_CRITICAL_M else "REDUCED"
    if weather.wind_speed >= WIND_WARNING_KT:
        ground = "RESTRICTED" if weather.wind_speed >= WIND_CRITICAL_KT else "CAUTION"

    return OperationalImpact(
        arrival_operations=arrival,
        departure_operations=departure,
        runway_operations=runway_ops,
        taxiway_visibility=taxi,
        ground_handling=ground,
        passenger_processing=pax,
        arrival_rate=arrival_rate,
        runway_status=runway_status,
        overall_status=overall,
        assessed_at=now,
        icao_code=weather.icao_code,
    )


def compute_weather_trends(
    current: WeatherObservation,
    previous: Optional[WeatherObservation],
) -> WeatherTrend:
    """Compare current vs previous observation for trend arrows."""
    if previous is None:
        return WeatherTrend(
            temperature="→",
            wind="→",
            visibility="Stable",
            humidity="→",
            rainfall="→",
            summary="Insufficient history — baseline observation recorded.",
        )

    def arrow(curr: float, prev: float, *, eps: float = 0.3) -> str:
        delta = curr - prev
        if abs(delta) <= eps:
            return "→"
        return "↑" if delta > 0 else "↓"

    vis_delta = current.visibility - previous.visibility
    if abs(vis_delta) < 100:
        vis_label = "Stable"
    elif vis_delta > 0:
        vis_label = "Improving"
    else:
        vis_label = "Declining"

    return WeatherTrend(
        temperature=arrow(current.temperature, previous.temperature, eps=0.4),
        wind=arrow(current.wind_speed, previous.wind_speed, eps=0.5),
        visibility=vis_label,
        humidity=arrow(current.humidity, previous.humidity, eps=1.0),
        rainfall=arrow(current.rainfall, previous.rainfall, eps=0.2),
        summary=(
            f"Visibility {vis_label.lower()}; temp {arrow(current.temperature, previous.temperature)}; "
            f"wind {arrow(current.wind_speed, previous.wind_speed)}."
        ),
    )


def _build_alert(
    *,
    title: str,
    description: str,
    severity: AlertSeverity,
    condition: str,
    affected: list[str],
    action: str,
    checklist: list[str],
    weather: WeatherObservation,
    now: datetime,
) -> WeatherAlert:
    meta = SEVERITY_META[severity]
    return WeatherAlert(
        id=_new_id("alert"),
        title=title,
        description=description,
        severity=severity,
        color=meta["color"],
        icon=meta["icon"],
        condition=condition,
        affected_operations=affected,
        recommended_action=action,
        checklist=checklist,
        timestamp=now,
        status=AlertStatus.ACTIVE,
        icao_code=weather.icao_code,
    )
