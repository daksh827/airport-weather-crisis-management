"""AOCC AI Assistant — Phase 7A live ops + Phase 7B RAG/Gemini."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.alert_service import AlertService, get_alert_service
from backend.services.flight_service import (
    FlightOperationsService,
    get_flight_operations_service,
)
from backend.services.ground_service import (
    GroundOperationsService,
    get_ground_operations_service,
)
from backend.services.impact_service import ImpactService, get_impact_service
from backend.services.incident_service import IncidentService, get_incident_service
from backend.services.kpi_service import AirportKPIService, get_airport_kpi_service
from backend.services.recommendation_service import (
    RecommendationService,
    get_recommendation_service,
)
from backend.services.runway_service import (
    RunwayOperationsService,
    get_runway_operations_service,
)
from backend.services.severity_service import SeverityService, get_severity_service
from backend.services.terminal_service import (
    TerminalOperationsService,
    get_terminal_operations_service,
)
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)

_UNKNOWN_REPLY = (
    "I don't currently have operational data for that request. "
    "Try asking about live weather, flights, runway, terminals, ground ops, "
    "incidents, KPIs, recommendations, or procedures from the Airport Weather "
    "Crisis Management Manual."
)

_HIGH_SEVERITIES = {"high", "critical", "level 3"}

_KNOWLEDGE_TOKENS = (
    "procedure",
    "protocol",
    "sop",
    "manual",
    "what should aocc",
    "what should the aocc",
    "during dense fog",
    "dense fog",
    "runway closure",
    "passenger communication",
    "thunderstorm response",
    "thunderstorm",
    "how should airlines",
    "airline coordination",
    "when should level",
    "level 3 be declared",
    "declare level",
    "contingency",
    "guidance in the manual",
    "according to the manual",
    "explain ",
)

_HYBRID_TOKENS = (
    "why is the airport",
    "why is airport",
    "operating with restrictions",
    "why level",
    "why are we",
    "why are these",
    "based on current",
    "given current",
)


class Intent(str, Enum):
    GREETING = "greeting"
    HELP = "help"
    WEATHER = "weather"
    VISIBILITY = "visibility"
    WIND = "wind"
    SEVERITY = "severity"
    ALERTS = "alerts"
    FLIGHTS = "flights"
    RUNWAY = "runway"
    TERMINAL = "terminal"
    GROUND = "ground"
    INCIDENTS = "incidents"
    KPI = "kpi"
    RECOMMENDATIONS = "recommendations"
    IMPACT = "impact"
    SUMMARY = "summary"
    KNOWLEDGE = "knowledge"
    UNKNOWN = "unknown"


class RouteMode(str, Enum):
    LIVE = "live"
    KNOWLEDGE = "knowledge"
    HYBRID = "hybrid"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def detect_intent(message: str) -> Intent:
    """Route the operator question to the relevant operational domain."""
    text = message.strip().lower()
    if not text:
        return Intent.UNKNOWN

    if _contains_any(text, ("hello", "hi ", "hi,", "hey", "good morning", "good evening")):
        return Intent.GREETING
    if text in {"hi", "hello", "hey"}:
        return Intent.GREETING
    if _contains_any(text, ("help", "what can you", "commands", "capabilities")):
        return Intent.HELP

    # Knowledge / SOP style questions (Phase 7B)
    if _contains_any(text, _KNOWLEDGE_TOKENS) or re.search(r"\brag\b", text):
        return Intent.KNOWLEDGE

    if _contains_any(
        text,
        (
            "airport summary",
            "operational summary",
            "summarize the airport",
            "summarise the airport",
            "give me an airport summary",
            "overall status",
            "operational status",
            "biggest operational",
            "biggest issues",
            "complete picture",
            "full status",
        ),
    ):
        return Intent.SUMMARY

    if _contains_any(
        text,
        (
            "recommend",
            "decision support",
            "which department",
            "who should respond",
            "why are these recommendation",
            "what actions",
            "operational guidance",
        ),
    ):
        return Intent.RECOMMENDATIONS

    if _contains_any(
        text,
        (
            "open incident",
            "active incident",
            "high severity incident",
            "incident",
            "crisis desk",
        ),
    ):
        return Intent.INCIDENTS

    if _contains_any(
        text,
        (
            "passenger count",
            "passengers today",
            "operational efficiency",
            "average delay",
            "average flight delay",
            "kpi",
            "flights today",
            "airport status",
        ),
    ):
        return Intent.KPI

    if _contains_any(
        text,
        (
            "fuel truck",
            "ground operation",
            "ground fleet",
            "baggage vehicle",
            "ground status",
            "gse",
        ),
    ):
        return Intent.GROUND

    if _contains_any(
        text,
        (
            "terminal",
            "passenger load",
            "busiest terminal",
            "security queue",
            "boarding gate",
        ),
    ):
        return Intent.TERMINAL

    if _contains_any(
        text,
        (
            "runway",
            "runway status",
            "runway capacity",
            "runway inspection",
        ),
    ):
        return Intent.RUNWAY

    if _contains_any(
        text,
        (
            "delayed flight",
            "flight delay",
            "how many delayed",
            "departures restricted",
            "departure",
            "arrival",
            "cancelled flight",
            "diverted",
            "flight operation",
        ),
    ):
        return Intent.FLIGHTS

    if _contains_any(text, ("operational impact", "ops impact", "arrival rate")):
        return Intent.IMPACT

    if _contains_any(text, ("visibility", "fog", "lvp", "rvr")):
        return Intent.VISIBILITY
    if _contains_any(text, ("wind", "gust", "crosswind")):
        return Intent.WIND

    if _contains_any(
        text,
        (
            "why is the airport level",
            "why level",
            "severity",
            "level 1",
            "level 2",
            "level 3",
            "crisis level",
            "alert level",
        ),
    ):
        return Intent.SEVERITY

    if _contains_any(text, ("weather alert", "active alert", "current alert")):
        return Intent.ALERTS

    if _contains_any(
        text,
        (
            "current weather",
            "weather",
            "metar",
            "temperature",
            "humidity",
            "rainfall",
            "pressure",
            "conditions",
        ),
    ):
        return Intent.WEATHER

    if _contains_any(text, ("status", "summary", "situation")):
        return Intent.SUMMARY

    return Intent.UNKNOWN


def detect_route(message: str, intent: Intent) -> RouteMode:
    """Decide whether to use live data, knowledge retrieval, or both."""
    text = message.strip().lower()

    if intent in {Intent.GREETING, Intent.HELP}:
        return RouteMode.LIVE

    if intent == Intent.KNOWLEDGE:
        if _contains_any(text, _HYBRID_TOKENS) or intent_needs_live_snapshot(text):
            return RouteMode.HYBRID
        return RouteMode.KNOWLEDGE

    if _contains_any(text, _HYBRID_TOKENS):
        return RouteMode.HYBRID

    if intent == Intent.UNKNOWN:
        # Fall back to knowledge search for open procedural questions
        if "?" in text or _contains_any(text, ("how ", "what ", "when ", "explain")):
            return RouteMode.KNOWLEDGE
        return RouteMode.LIVE

    if intent in {
        Intent.SEVERITY,
        Intent.RECOMMENDATIONS,
        Intent.SUMMARY,
        Intent.IMPACT,
    } and _contains_any(
        text,
        (
            "why",
            "procedure",
            "should",
            "protocol",
            "restrictions",
            "declare",
            "response",
        ),
    ):
        return RouteMode.HYBRID

    return RouteMode.LIVE


def intent_needs_live_snapshot(text: str) -> bool:
    return _contains_any(
        text,
        (
            "current",
            "right now",
            "today",
            "live",
            "level 2",
            "level 3",
            "restrictions",
        ),
    )


class AssistantService:
    """Live-data + RAG AOCC assistant that reuses existing operational services."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherService] = None,
        severity_service: Optional[SeverityService] = None,
        alert_service: Optional[AlertService] = None,
        impact_service: Optional[ImpactService] = None,
        flight_service: Optional[FlightOperationsService] = None,
        runway_service: Optional[RunwayOperationsService] = None,
        terminal_service: Optional[TerminalOperationsService] = None,
        ground_service: Optional[GroundOperationsService] = None,
        kpi_service: Optional[AirportKPIService] = None,
        incident_service: Optional[IncidentService] = None,
        recommendation_service: Optional[RecommendationService] = None,
        knowledge_rag_service=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.weather_service = weather_service or get_weather_service()
        self.severity_service = severity_service or get_severity_service()
        self.alert_service = alert_service or get_alert_service()
        self.impact_service = impact_service or get_impact_service()
        self.flight_service = flight_service or get_flight_operations_service()
        self.runway_service = runway_service or get_runway_operations_service()
        self.terminal_service = terminal_service or get_terminal_operations_service()
        self.ground_service = ground_service or get_ground_operations_service()
        self.kpi_service = kpi_service or get_airport_kpi_service()
        self.incident_service = incident_service or get_incident_service()
        self.recommendation_service = (
            recommendation_service or get_recommendation_service()
        )
        self._knowledge_rag_service = knowledge_rag_service

    @property
    def knowledge_rag_service(self):
        if self._knowledge_rag_service is None:
            from backend.rag.rag_service import get_knowledge_rag_service

            self._knowledge_rag_service = get_knowledge_rag_service(self.settings)
        return self._knowledge_rag_service

    def chat(self, message: str, session_id: Optional[str] = None) -> dict:
        intent = detect_intent(message)
        mode = detect_route(message, intent)
        provider = "aocc-live"
        sources: list[str] = []
        retrieved_chunks = 0

        try:
            if mode == RouteMode.LIVE:
                reply = self._answer_live(intent, message)
                provider = "aocc-live"
            elif mode == RouteMode.KNOWLEDGE:
                rag = self.knowledge_rag_service.answer(message)
                reply = rag["reply"]
                provider = rag.get("provider") or "aocc-rag"
                sources = rag.get("sources") or []
                retrieved_chunks = int(rag.get("retrieved_chunks") or 0)
            else:
                live_context = self._build_live_context(intent, message)
                rag = self.knowledge_rag_service.answer(
                    message,
                    live_context=live_context,
                )
                reply = rag["reply"]
                provider = "aocc-hybrid"
                sources = rag.get("sources") or []
                retrieved_chunks = int(rag.get("retrieved_chunks") or 0)
        except Exception:
            logger.exception("Assistant failed intent=%s mode=%s", intent.value, mode.value)
            if mode == RouteMode.LIVE:
                reply = (
                    "I encountered an issue retrieving live operational data. "
                    "Please retry in a moment."
                )
            else:
                reply = (
                    "I encountered an issue retrieving manual guidance. "
                    "Please retry in a moment."
                )

        logger.info(
            "Assistant intent=%s mode=%s provider=%s message=%r",
            intent.value,
            mode.value,
            provider,
            message[:80],
        )
        return {
            "reply": reply,
            "provider": provider,
            "context_used": mode != RouteMode.LIVE or intent != Intent.UNKNOWN,
            "intent": intent.value,
            "route": mode.value,
            "sources": sources,
            "retrieved_chunks": retrieved_chunks,
            "timestamp": _utc_now().isoformat(),
            "session_id": session_id or str(uuid.uuid4()),
        }

    def _answer_live(self, intent: Intent, message: str) -> str:
        handlers = {
            Intent.GREETING: self._reply_greeting,
            Intent.HELP: self._reply_help,
            Intent.WEATHER: self._reply_weather,
            Intent.VISIBILITY: self._reply_visibility,
            Intent.WIND: self._reply_wind,
            Intent.SEVERITY: self._reply_severity,
            Intent.ALERTS: self._reply_alerts,
            Intent.FLIGHTS: self._reply_flights,
            Intent.RUNWAY: self._reply_runway,
            Intent.TERMINAL: self._reply_terminal,
            Intent.GROUND: self._reply_ground,
            Intent.INCIDENTS: lambda msg: self._reply_incidents(msg),
            Intent.KPI: self._reply_kpi,
            Intent.RECOMMENDATIONS: self._reply_recommendations,
            Intent.IMPACT: self._reply_impact,
            Intent.SUMMARY: self._reply_summary,
        }
        handler = handlers.get(intent)
        if handler is None:
            return _UNKNOWN_REPLY
        return handler(message)

    def _build_live_context(self, intent: Intent, message: str) -> str:
        """Compact live snapshot for hybrid Gemini prompts."""
        try:
            if intent in {Intent.SEVERITY, Intent.SUMMARY, Intent.KNOWLEDGE, Intent.UNKNOWN}:
                return self._reply_summary(message)
            if intent == Intent.RECOMMENDATIONS:
                return self._reply_recommendations(message)
            if intent == Intent.WEATHER:
                return self._reply_weather(message)
            if intent == Intent.VISIBILITY:
                return self._reply_visibility(message)
            if intent == Intent.FLIGHTS:
                return self._reply_flights(message)
            if intent == Intent.RUNWAY:
                return self._reply_runway(message)
            if intent == Intent.IMPACT:
                return self._reply_impact(message)
            return self._reply_summary(message)
        except Exception:
            logger.exception("Failed building live context for hybrid answer")
            return "Live operational context temporarily unavailable."

    def _reply_greeting(self, _message: str) -> str:
        weather = self.weather_service.get_current_weather()
        severity = self.severity_service.assess_from_weather(weather)
        return (
            f"AOCC AI Assistant online for {weather.icao_code} "
            f"({weather.airport_name}).\n\n"
            f"Current severity: {severity.title}\n"
            f"Weather: {weather.weather_description}\n\n"
            "Ask about live operations or procedures from the Airport Weather "
            "Crisis Management Manual."
        )

    def _reply_help(self, _message: str) -> str:
        return (
            "I answer from live AOCC operational data and the Airport Weather "
            "Crisis Management Manual (RAG).\n\n"
            "Live examples:\n"
            "• What is the current weather?\n"
            "• How many delayed flights?\n"
            "• Current runway status?\n"
            "• How many open incidents?\n"
            "• Give me an airport summary.\n\n"
            "Manual / procedure examples:\n"
            "• What should AOCC do during dense fog?\n"
            "• What is the runway closure procedure?\n"
            "• Explain thunderstorm response.\n"
            "• When should Level 3 be declared?"
        )

    def _reply_weather(self, _message: str) -> str:
        weather = self.weather_service.get_current_weather()
        severity = self.severity_service.assess_from_weather(weather)
        return (
            f"Current Weather — {weather.icao_code}\n\n"
            f"Conditions: {weather.weather_description}\n"
            f"Temperature: {weather.temperature}°C\n"
            f"Visibility: {weather.visibility:.0f} m\n"
            f"Wind: {weather.wind_speed} kt from {weather.wind_direction}\n"
            f"Rainfall: {weather.rainfall} mm\n"
            f"Pressure: {weather.pressure} hPa\n"
            f"Humidity: {weather.humidity}%\n"
            f"Severity: {severity.title}\n"
            f"Source: {weather.source}"
        )

    def _reply_visibility(self, _message: str) -> str:
        weather = self.weather_service.get_current_weather()
        severity = self.severity_service.assess_from_weather(weather)
        return (
            f"Visibility at {weather.icao_code}: {weather.visibility:.0f} m\n"
            f"Conditions: {weather.weather_description}\n"
            f"Severity: {severity.title}"
        )

    def _reply_wind(self, _message: str) -> str:
        weather = self.weather_service.get_current_weather()
        return (
            f"Wind at {weather.icao_code}: {weather.wind_speed} kt "
            f"from {weather.wind_direction}\n"
            f"Conditions: {weather.weather_description}"
        )

    def _reply_severity(self, _message: str) -> str:
        weather = self.weather_service.get_current_weather()
        severity = self.severity_service.assess_from_weather(weather)
        factors = "; ".join(severity.contributing_factors) or "None listed"
        return (
            f"Airport Severity — Level {severity.level.value}\n\n"
            f"Status: {severity.title}\n"
            f"Description: {severity.description}\n"
            f"Contributing factors: {factors}\n"
            f"Weather: {weather.weather_description}\n"
            f"Visibility: {weather.visibility:.0f} m\n"
            f"Recommended action: {severity.recommended_action}"
        )

    def _reply_alerts(self, _message: str) -> str:
        package = self.alert_service.get_current()
        current = package.get("current") or {}
        active = package.get("active_alerts") or []
        if not current and not active:
            return "No active weather alerts at this time."
        lines = [
            "Weather Alerts",
            "",
            f"Primary: {current.get('title', '—')} ({current.get('severity', '—')})",
            f"Condition: {current.get('condition', '—')}",
            f"Recommended action: {current.get('recommended_action', '—')}",
            f"Active alerts: {len(active)}",
        ]
        for alert in active[:5]:
            lines.append(
                f"• {alert.get('title', 'Alert')} — {alert.get('severity', '—')}"
            )
        return "\n".join(lines)

    def _reply_flights(self, message: str) -> str:
        flights = self.flight_service.get_flight_operations()
        text = message.lower()
        if "delayed" in text:
            return (
                f"Delayed Flights: {flights.get('delayed', 0)}\n"
                f"Cancelled: {flights.get('cancelled', 0)}\n"
                f"Diverted: {flights.get('diverted', 0)}\n"
                f"Severity Level: {flights.get('severity_level', '—')}"
            )
        if "depart" in text:
            return (
                f"Departures: {flights.get('departures', 0)}\n"
                f"Delayed: {flights.get('delayed', 0)}\n"
                f"Cancelled: {flights.get('cancelled', 0)}\n"
                f"Severity Level: {flights.get('severity_level', '—')}"
            )
        return (
            f"Flight Operations — {flights.get('icao_code', self.settings.airport_icao)}\n\n"
            f"Arrivals: {flights.get('arrivals', 0)}\n"
            f"Departures: {flights.get('departures', 0)}\n"
            f"Delayed: {flights.get('delayed', 0)}\n"
            f"Cancelled: {flights.get('cancelled', 0)}\n"
            f"Diverted: {flights.get('diverted', 0)}\n"
            f"Severity Level: {flights.get('severity_level', '—')}"
        )

    def _reply_runway(self, _message: str) -> str:
        runway = self.runway_service.get_runway_operations()
        return (
            f"Runway Operations — {runway.get('icao_code', self.settings.airport_icao)}\n\n"
            f"Runway: {runway.get('runway_number', '—')}\n"
            f"Status: {runway.get('status', '—')}\n"
            f"Surface: {runway.get('surface', '—')}\n"
            f"Inspection: {runway.get('inspection', '—')}\n"
            f"Lighting: {runway.get('lighting', '—')}\n"
            f"Severity Level: {runway.get('severity_level', '—')}"
        )

    def _reply_terminal(self, message: str) -> str:
        terminals = self.terminal_service.get_terminal_operations()
        text = message.lower()
        keys = ("terminal1", "terminal2", "terminal3")
        labels = {
            "terminal1": "Terminal 1",
            "terminal2": "Terminal 2",
            "terminal3": "Terminal 3",
        }

        requested = None
        for key, label in labels.items():
            num = key[-1]
            if f"terminal {num}" in text or f"terminal{num}" in text or f"t{num}" in text:
                requested = key
                break

        if requested and isinstance(terminals.get(requested), dict):
            t = terminals[requested]
            return (
                f"{labels[requested]} Status\n\n"
                f"Passenger load: {t.get('passenger_load', '—')}\n"
                f"Occupied gates: {t.get('occupied_gates', '—')}\n"
                f"Available gates: {t.get('available_gates', '—')}\n"
                f"Security queue: {t.get('security_queue', '—')}\n"
                f"Boarding gates: {t.get('boarding_gates', '—')}"
            )

        loads = []
        load_rank = {"NORMAL": 1, "BUSY": 2, "CRITICAL": 3, "HIGH": 3, "LOW": 0}
        for key in keys:
            block = terminals.get(key) or {}
            load = str(block.get("passenger_load") or "")
            rank = load_rank.get(load.upper())
            if rank is None:
                try:
                    rank = float(load.replace("%", ""))
                except (TypeError, ValueError):
                    rank = -1.0
            loads.append((key, rank, load or "—"))
        busiest = max(loads, key=lambda row: row[1]) if loads else None

        lines = [
            f"Terminal Operations — {terminals.get('icao_code', self.settings.airport_icao)}",
            "",
        ]
        for key in keys:
            t = terminals.get(key) or {}
            lines.append(
                f"{labels[key]}: load {t.get('passenger_load', '—')}, "
                f"queue {t.get('security_queue', '—')}, "
                f"gates {t.get('occupied_gates', '—')}/{t.get('available_gates', '—')}"
            )
        if busiest and busiest[1] >= 0:
            lines.append("")
            lines.append(f"Busiest terminal: {labels[busiest[0]]} ({busiest[2]})")
        return "\n".join(lines)

    def _reply_ground(self, message: str) -> str:
        ground = self.ground_service.get_ground_operations()
        text = message.lower()
        fuel = ground.get("fuel_trucks") or {}
        if "fuel" in text:
            return (
                f"Fuel Trucks Available: {fuel.get('available', '—')}\n"
                f"In use: {fuel.get('in_use', '—')}\n"
                f"Maintenance: {fuel.get('maintenance', '—')}\n"
                f"Ground status: {ground.get('ground_status', '—')}\n"
                f"Fleet availability: {ground.get('fleet_availability_pct', '—')}%"
            )
        lines = [
            f"Ground Operations — {ground.get('icao_code', self.settings.airport_icao)}",
            "",
            f"Status: {ground.get('ground_status', '—')}",
            f"Fleet availability: {ground.get('fleet_availability_pct', '—')}%",
            "",
        ]
        for key, label in (
            ("fuel_trucks", "Fuel trucks"),
            ("baggage_vehicles", "Baggage vehicles"),
            ("pushback_vehicles", "Pushback vehicles"),
            ("catering_vehicles", "Catering vehicles"),
            ("maintenance_vehicles", "Maintenance vehicles"),
            ("follow_me_vehicles", "Follow-me vehicles"),
        ):
            block = ground.get(key)
            if isinstance(block, dict):
                lines.append(
                    f"{label}: available {block.get('available', '—')}, "
                    f"in use {block.get('in_use', '—')}, "
                    f"maintenance {block.get('maintenance', '—')}"
                )
        return "\n".join(lines)

    def _reply_incidents(self, message: str) -> str:
        text = message.lower()
        stats = self.incident_service.get_stats()

        if "high severity" in text or "critical" in text or "level 3" in text:
            data = self.incident_service.list_incidents()
            items = [
                item
                for item in data.get("items", [])
                if str(item.get("severity", "")).lower() in _HIGH_SEVERITIES
                and str(item.get("status", "")).lower()
                not in {"resolved", "closed"}
            ]
            if not items:
                return "No high-severity active incidents at this time."
            lines = [f"High Severity Active Incidents: {len(items)}", ""]
            for item in items[:8]:
                lines.append(
                    f"• {item.get('incident_id')} — {item.get('incident_type')} "
                    f"({item.get('severity')}) | {item.get('status')} | "
                    f"{item.get('assigned_department')}"
                )
            return "\n".join(lines)

        if "open" in text:
            return (
                f"Open Incidents: {stats.get('open_incidents', 0)}\n"
                f"Assigned: {stats.get('assigned', 0)}\n"
                f"In Progress: {stats.get('in_progress', 0)}"
            )

        data = self.incident_service.list_incidents()
        active = [
            item
            for item in data.get("items", [])
            if str(item.get("status", "")).lower() not in {"resolved", "closed"}
        ]
        lines = [
            "Active Incidents",
            "",
            f"Open: {stats.get('open_incidents', 0)}",
            f"Assigned: {stats.get('assigned', 0)}",
            f"In Progress: {stats.get('in_progress', 0)}",
            f"Resolved today: {stats.get('resolved_today', 0)}",
            f"Active listed: {len(active)}",
            "",
        ]
        for item in active[:6]:
            lines.append(
                f"• {item.get('incident_id')} — {item.get('incident_type')} "
                f"({item.get('severity')}) | {item.get('status')} | "
                f"{item.get('assigned_department')}"
            )
        if not active:
            lines.append("No active incidents currently listed.")
        return "\n".join(lines)

    def _reply_kpi(self, message: str) -> str:
        kpis = self.kpi_service.get_kpis()
        text = message.lower()
        if "passenger" in text:
            return f"Today's passenger count: {kpis.get('passengers_today', '—')}"
        if "efficiency" in text:
            return (
                f"Airport operational efficiency: "
                f"{kpis.get('operational_efficiency', '—')}%"
            )
        if (
            "average delay" in text
            or "average flight delay" in text
            or "avg delay" in text
            or ("delay" in text and "average" in text)
        ):
            return f"Average flight delay: {kpis.get('average_delay', '—')} min"
        return (
            f"Airport KPIs — {kpis.get('icao_code', self.settings.airport_icao)}\n\n"
            f"Airport Status: {kpis.get('airport_status', '—')}\n"
            f"Flights today: {kpis.get('flights_today', '—')}\n"
            f"Passengers today: {kpis.get('passengers_today', '—')}\n"
            f"Delayed flights: {kpis.get('delayed_flights', '—')}\n"
            f"Cancelled flights: {kpis.get('cancelled_flights', '—')}\n"
            f"Average delay: {kpis.get('average_delay', '—')} min\n"
            f"Runway availability: {kpis.get('runway_availability', '—')}%\n"
            f"Terminal utilization: {kpis.get('terminal_utilization', '—')}%\n"
            f"Ground vehicle availability: {kpis.get('ground_vehicle_availability', '—')}%\n"
            f"Operational efficiency: {kpis.get('operational_efficiency', '—')}%"
        )

    def _reply_recommendations(self, message: str) -> str:
        reco = self.recommendation_service.get_recommendations()
        items = reco.get("recommendations") or []
        text = message.lower()

        if "department" in text or "respond first" in text:
            high = [r for r in items if str(r.get("priority", "")).lower() == "high"]
            focus = high[0] if high else (items[0] if items else None)
            if not focus:
                return "No active departmental recommendations at this time."
            return (
                f"Priority response department: {focus.get('department', 'AOCC')}\n"
                f"Action: {focus.get('title', '—')}\n"
                f"Priority: {focus.get('priority', '—')}\n"
                f"Detail: {focus.get('description', '—')}"
            )

        if "why" in text:
            severity = self.severity_service.assess_current()
            factors = "; ".join(severity.contributing_factors) or "Current operational state"
            return (
                f"Recommendations are active because severity is "
                f"Level {severity.level.value} ({severity.title}).\n"
                f"Drivers: {factors}\n"
                f"Overall decision: {reco.get('overall_decision', '—')}"
            )

        lines = [
            "AOCC Recommended Actions",
            "",
            f"Overall decision: {reco.get('overall_decision', '—')}",
            f"Severity Level: {reco.get('severity_level', '—')}",
            "",
        ]
        if not items:
            lines.append("No recommendations currently active.")
        for idx, item in enumerate(items[:6], start=1):
            lines.append(
                f"{idx}. [{item.get('priority', '—')}] {item.get('title', 'Action')} "
                f"— {item.get('department', 'AOCC')}\n"
                f"   {item.get('description', '')}"
            )
        return "\n".join(lines)

    def _reply_impact(self, _message: str) -> str:
        impact = self.impact_service.get_impact()
        return (
            f"Operational Impact — {impact.get('icao_code', self.settings.airport_icao)}\n\n"
            f"Overall status: {impact.get('overall_status', '—')}\n"
            f"Arrival operations: {impact.get('arrival_operations', '—')}\n"
            f"Departure operations: {impact.get('departure_operations', '—')}\n"
            f"Runway operations: {impact.get('runway_operations', '—')}\n"
            f"Runway status: {impact.get('runway_status', '—')}\n"
            f"Arrival rate: {impact.get('arrival_rate', '—')}\n"
            f"Taxiway visibility: {impact.get('taxiway_visibility', '—')}\n"
            f"Ground handling: {impact.get('ground_handling', '—')}\n"
            f"Passenger processing: {impact.get('passenger_processing', '—')}"
        )

    def _reply_summary(self, message: str) -> str:
        weather = self.weather_service.get_current_weather()
        severity = self.severity_service.assess_from_weather(weather)
        flights = self.flight_service.get_flight_operations()
        runway = self.runway_service.get_runway_operations()
        ground = self.ground_service.get_ground_operations()
        kpis = self.kpi_service.get_kpis()
        incidents = self.incident_service.get_stats()
        reco = self.recommendation_service.get_recommendations()
        impact = self.impact_service.get_impact()

        top_action = "Monitor evolving conditions."
        items = reco.get("recommendations") or []
        if items:
            top = items[0]
            top_action = (
                f"{top.get('title', 'Follow AOCC guidance')} "
                f"({top.get('department', 'AOCC')})"
            )

        text = message.lower()
        if "biggest" in text or "issue" in text:
            issues = []
            if int(flights.get("delayed") or 0) > 0:
                issues.append(f"{flights.get('delayed')} delayed flights")
            if str(runway.get("status", "")).upper() != "OPEN":
                issues.append(f"Runway {runway.get('status', 'constrained')}")
            if int(incidents.get("open_incidents") or 0) > 0:
                issues.append(f"{incidents.get('open_incidents')} open incidents")
            if severity.level.value >= 2:
                issues.append(f"Severity {severity.title}")
            if not issues:
                issues.append("No major operational issues identified from live data")
            return (
                "Today's Biggest Operational Issues\n\n"
                + "\n".join(f"• {item}" for item in issues)
                + f"\n\nRecommended Action:\n{top_action}"
            )

        return (
            "Airport Operational Summary\n\n"
            f"Airport Status:\n{kpis.get('airport_status') or impact.get('overall_status') or severity.title}\n\n"
            f"Weather:\n{weather.weather_description}\n\n"
            f"Severity:\nLevel {severity.level.value}\n\n"
            f"Visibility:\n{weather.visibility:.0f} m\n\n"
            f"Delayed Flights:\n{flights.get('delayed', 0)}\n\n"
            f"Open Incidents:\n{incidents.get('open_incidents', 0)}\n\n"
            f"Runway Status:\n{runway.get('status', '—')}\n\n"
            f"Ground Fleet Availability:\n{ground.get('fleet_availability_pct', '—')}%\n\n"
            f"Operational Efficiency:\n{kpis.get('operational_efficiency', '—')}%\n\n"
            f"Recommended Action:\n{top_action}"
        )


def get_assistant_service() -> AssistantService:
    """FastAPI dependency factory for the live AOCC assistant."""
    return AssistantService()
