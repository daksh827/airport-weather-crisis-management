"""AI Operations Decision Support — rule-based AOCC recommendation engine.

Aggregates live weather, severity, alerts, and Phase 5A/5B ops summaries
into an overall airport decision plus prioritized action cards.
This is not a chatbot and does not use RAG.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.alert_service import AlertService, get_alert_service
from backend.services.flight_service import FlightOperationsService, get_flight_operations_service
from backend.services.ground_service import GroundOperationsService, get_ground_operations_service
from backend.services.kpi_service import AirportKPIService, get_airport_kpi_service
from backend.services.runway_service import RunwayOperationsService, get_runway_operations_service
from backend.services.severity_service import SeverityService, get_severity_service
from backend.services.terminal_service import TerminalOperationsService, get_terminal_operations_service
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)

_DECISION_NORMAL = "Airport Operating Normally"
_DECISION_RESTRICTED = "Airport Operating With Restrictions"
_DECISION_SEVERE = "Airport Operating Under Severe Weather"
_DECISION_CRITICAL = "Airport Critical Operations"
_DECISION_EMERGENCY = "Airport Emergency Operations"


def _rec(
    title: str,
    description: str,
    priority: str,
    department: str,
    status: str = "Recommended",
) -> dict:
    return {
        "title": title,
        "description": description,
        "priority": priority,
        "department": department,
        "status": status,
    }


class RecommendationService:
    """Rule-based operational recommendation engine for AOCC operators."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherService] = None,
        severity_service: Optional[SeverityService] = None,
        alert_service: Optional[AlertService] = None,
        flight_service: Optional[FlightOperationsService] = None,
        runway_service: Optional[RunwayOperationsService] = None,
        terminal_service: Optional[TerminalOperationsService] = None,
        ground_service: Optional[GroundOperationsService] = None,
        kpi_service: Optional[AirportKPIService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.weather_service = weather_service or get_weather_service()
        self.severity_service = severity_service or get_severity_service()
        self.alert_service = alert_service or get_alert_service()
        self.flight_service = flight_service or get_flight_operations_service()
        self.runway_service = runway_service or get_runway_operations_service()
        self.terminal_service = terminal_service or get_terminal_operations_service()
        self.ground_service = ground_service or get_ground_operations_service()
        self.kpi_service = kpi_service or get_airport_kpi_service()

    def get_recommendations(self, icao_code: Optional[str] = None) -> dict:
        icao = (icao_code or self.settings.airport_icao).upper()

        weather = self.weather_service.get_current_weather(icao)
        assessment = self.severity_service.assess_current(icao)
        level = int(assessment.level.value)
        alert_bundle = self.alert_service.get_current(icao)
        flights = self.flight_service.get_flight_operations(icao)
        runway = self.runway_service.get_runway_operations(icao)
        terminals = self.terminal_service.get_terminal_operations(icao)
        ground = self.ground_service.get_ground_operations(icao)
        kpis = self.kpi_service.get_kpis(icao)

        overall_decision = self._overall_decision(level, runway, alert_bundle, kpis)
        recommendations = self._build_recommendations(
            level=level,
            weather=weather,
            assessment=assessment,
            alert_bundle=alert_bundle,
            flights=flights,
            runway=runway,
            terminals=terminals,
            ground=ground,
            kpis=kpis,
        )

        data = {
            "overall_decision": overall_decision,
            "recommendations": recommendations,
            "severity_level": level,
            "icao_code": icao,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Recommendations for %s (L%s): decision=%s count=%s",
            icao,
            level,
            overall_decision,
            len(recommendations),
        )
        return data

    def _overall_decision(
        self,
        level: int,
        runway: dict,
        alert_bundle: dict,
        kpis: dict,
    ) -> str:
        runway_status = str(runway.get("status", "OPEN")).upper()
        primary = alert_bundle.get("current") or {}
        alert_severity = str(primary.get("severity") or "").upper()
        airport_status = str(kpis.get("airport_status", "")).upper()

        if level >= 3 and (
            runway_status == "CLOSED"
            or alert_severity in {"CRITICAL", "EMERGENCY", "CRISIS"}
            or "DISRUPTED" in airport_status
            or "CLOSED" in airport_status
        ):
            if runway_status == "CLOSED" or alert_severity in {"EMERGENCY", "CRISIS"}:
                return _DECISION_EMERGENCY
            return _DECISION_CRITICAL

        if level >= 3:
            return _DECISION_SEVERE
        if level == 2:
            return _DECISION_RESTRICTED
        return _DECISION_NORMAL

    def _build_recommendations(
        self,
        *,
        level: int,
        weather,
        assessment,
        alert_bundle: dict,
        flights: dict,
        runway: dict,
        terminals: dict,
        ground: dict,
        kpis: dict,
    ) -> list[dict]:
        items: list[dict] = []

        if level <= 1:
            items.extend(self._level1_base())
        elif level == 2:
            items.extend(self._level2_base())
        else:
            items.extend(self._level3_base(runway))

        items.extend(
            self._contextual(
                level=level,
                weather=weather,
                assessment=assessment,
                alert_bundle=alert_bundle,
                flights=flights,
                runway=runway,
                terminals=terminals,
                ground=ground,
                kpis=kpis,
            )
        )

        # Stable priority order: High → Medium → Low
        rank = {"High": 0, "Medium": 1, "Low": 2}
        items.sort(key=lambda r: (rank.get(r.get("priority", "Medium"), 1), r.get("title", "")))
        return items

    def _level1_base(self) -> list[dict]:
        return [
            _rec(
                "Continue Normal Airport Operations",
                "No weather restrictions require capacity cuts. Keep published schedules and standard staffing.",
                "Low",
                "AOCC",
                "Monitoring",
            ),
            _rec(
                "Monitor Weather Every 30 Minutes",
                "Retain the standard AOCC weather refresh cycle and watch for visibility or wind shifts.",
                "Low",
                "Meteorology",
                "Monitoring",
            ),
            _rec(
                "Maintain Normal Runway Capacity",
                "Keep full runway throughput and standard separation unless conditions deteriorate.",
                "Low",
                "ATC",
                "Recommended",
            ),
        ]

    def _level2_base(self) -> list[dict]:
        return [
            _rec(
                "Reduce Runway Throughput",
                "Reduce runway movements by approximately 20 percent until weather improves.",
                "High",
                "ATC",
                "Recommended",
            ),
            _rec(
                "Increase Passenger Announcements",
                "Raise terminal PA frequency for delays, gate changes, and weather advisories.",
                "Medium",
                "Terminal",
                "Recommended",
            ),
            _rec(
                "Prepare Standby Ground Crew",
                "Stage additional fuel, baggage, and pushback crews for extended turnaround times.",
                "Medium",
                "Ground Ops",
                "In Progress",
            ),
            _rec(
                "Monitor Visibility Continuously",
                "Track visibility and RVR trends continuously; brief ATC and airlines on changes.",
                "High",
                "Meteorology",
                "Monitoring",
            ),
        ]

    def _level3_base(self, runway: dict) -> list[dict]:
        runway_status = str(runway.get("status", "OPEN")).upper()
        items = [
            _rec(
                "Suspend Departures if Required",
                "Authorize departure holds when runway or weather limits cannot support safe release.",
                "High",
                "ATC",
                "Recommended",
            ),
            _rec(
                "Hold Arriving Aircraft if Necessary",
                "Coordinate airborne holding or diversions when arrival acceptance rates fall.",
                "High",
                "ATC",
                "Recommended",
            ),
            _rec(
                "Activate Airport Crisis Management Team",
                "Stand up the crisis cell for cross-department command, control, and airline liaison.",
                "High",
                "AOCC",
                "In Progress",
            ),
            _rec(
                "Close Affected Taxiways",
                "Close taxiways impacted by weather or low visibility procedures as required.",
                "High",
                "Airside",
                "Recommended",
            ),
            _rec(
                "Deploy Emergency Response Teams",
                "Pre-position ARFF and emergency response assets for elevated weather risk.",
                "High",
                "Emergency",
                "Recommended",
            ),
            _rec(
                "Coordinate With Airlines",
                "Align cancellations, delays, and passenger care plans with airline operations centers.",
                "Medium",
                "Airline Ops",
                "In Progress",
            ),
        ]
        if runway_status == "CLOSED":
            items.insert(
                0,
                _rec(
                    "Maintain Runway Closure Protocols",
                    "Keep the active runway closed until weather and surface conditions meet reopen criteria.",
                    "High",
                    "ATC",
                    "In Progress",
                ),
            )
        return items

    def _contextual(
        self,
        *,
        level: int,
        weather,
        assessment,
        alert_bundle: dict,
        flights: dict,
        runway: dict,
        terminals: dict,
        ground: dict,
        kpis: dict,
    ) -> list[dict]:
        extra: list[dict] = []

        # Weather-driven
        visibility = getattr(weather, "visibility", None)
        if visibility is not None and float(visibility) < 3000 and level >= 2:
            extra.append(
                _rec(
                    "Apply Low Visibility Procedures",
                    f"Observed visibility is {visibility} m. Enforce LVP spacing and approach minima.",
                    "High",
                    "ATC",
                    "Recommended",
                )
            )

        # Alert-driven
        primary = alert_bundle.get("current") or {}
        alert_title = primary.get("title") or primary.get("condition")
        alert_sev = str(primary.get("severity") or "").upper()
        if alert_title and level >= 2 and alert_sev not in {"", "NORMAL"}:
            extra.append(
                _rec(
                    "Execute Active Weather Alert Plan",
                    f"Primary alert \"{alert_title}\" is active. Follow the AOCC alert checklist and notify stakeholders.",
                    "High",
                    "AOCC",
                    "In Progress",
                )
            )

        # Flight pressure
        delayed = int(flights.get("delayed") or 0)
        cancelled = int(flights.get("cancelled") or 0)
        if delayed >= 40 or cancelled >= 8:
            extra.append(
                _rec(
                    "Manage Schedule Disruption",
                    f"Current disruption: {delayed} delayed and {cancelled} cancelled. Prioritize recovery slots and passenger rebooking.",
                    "Medium" if level < 3 else "High",
                    "Airline Ops",
                    "Recommended",
                )
            )

        # Terminal load
        for key, label in (
            ("terminal1", "Terminal 1"),
            ("terminal2", "Terminal 2"),
            ("terminal3", "Terminal 3"),
        ):
            block = terminals.get(key) or {}
            load = str(block.get("passenger_load", "")).upper()
            queue = str(block.get("security_queue", "")).upper()
            if load == "CRITICAL" or queue == "HIGH":
                extra.append(
                    _rec(
                        f"Relieve {label} Congestion",
                        f"{label} reports load={block.get('passenger_load')} and security queue={block.get('security_queue')}. Open extra lanes and redeploy staff.",
                        "High" if level >= 2 else "Medium",
                        "Terminal",
                        "Recommended",
                    )
                )
                break

        # Ground fleet
        ground_status = str(ground.get("ground_status", "")).upper()
        if ground_status in {"CONSTRAINED", "RESTRICTED"}:
            extra.append(
                _rec(
                    "Protect Ground Resource Availability",
                    f"Ground status is {ground_status} with fleet availability at {ground.get('fleet_availability_pct', '—')}%. Limit non-essential vehicle tasking.",
                    "Medium" if ground_status == "CONSTRAINED" else "High",
                    "Ground Ops",
                    "Monitoring",
                )
            )

        # KPI efficiency
        efficiency = kpis.get("operational_efficiency")
        if efficiency is not None and float(efficiency) < 90:
            extra.append(
                _rec(
                    "Raise Operational Efficiency Focus",
                    f"Operational efficiency is {efficiency}%. Target runway, terminal, and ground bottlenecks in the next ops brief.",
                    "Medium",
                    "AOCC",
                    "Monitoring",
                )
            )

        # Assessment guidance echo (single card, not duplicating severity panel)
        guidance = getattr(assessment, "recommended_action", None) or ""
        if guidance and level >= 2:
            extra.append(
                _rec(
                    "Follow Severity Engine Guidance",
                    str(guidance),
                    "Medium",
                    "AOCC",
                    "Recommended",
                )
            )

        return extra


def get_recommendation_service() -> RecommendationService:
    return RecommendationService()
