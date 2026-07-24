"""Terminal Operations Service — simulated T1/T2/T3 gate and passenger status."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import Settings, get_settings
from backend.services.severity_service import SeverityService, get_severity_service

logger = logging.getLogger(__name__)

# Baseline profiles per terminal (VIDP-style), keyed by severity level
_TERMINAL_BASELINES = {
    1: {
        "terminal1": {
            "occupied_gates": 22,
            "available_gates": 14,
            "passenger_load": "NORMAL",
            "security_queue": "LOW",
            "boarding_gates": 10,
        },
        "terminal2": {
            "occupied_gates": 18,
            "available_gates": 10,
            "passenger_load": "NORMAL",
            "security_queue": "LOW",
            "boarding_gates": 8,
        },
        "terminal3": {
            "occupied_gates": 48,
            "available_gates": 16,
            "passenger_load": "BUSY",
            "security_queue": "MEDIUM",
            "boarding_gates": 22,
        },
    },
    2: {
        "terminal1": {
            "occupied_gates": 28,
            "available_gates": 8,
            "passenger_load": "BUSY",
            "security_queue": "MEDIUM",
            "boarding_gates": 12,
        },
        "terminal2": {
            "occupied_gates": 24,
            "available_gates": 4,
            "passenger_load": "BUSY",
            "security_queue": "HIGH",
            "boarding_gates": 11,
        },
        "terminal3": {
            "occupied_gates": 58,
            "available_gates": 6,
            "passenger_load": "CRITICAL",
            "security_queue": "HIGH",
            "boarding_gates": 28,
        },
    },
    3: {
        "terminal1": {
            "occupied_gates": 32,
            "available_gates": 4,
            "passenger_load": "CRITICAL",
            "security_queue": "HIGH",
            "boarding_gates": 8,
        },
        "terminal2": {
            "occupied_gates": 26,
            "available_gates": 2,
            "passenger_load": "CRITICAL",
            "security_queue": "HIGH",
            "boarding_gates": 6,
        },
        "terminal3": {
            "occupied_gates": 62,
            "available_gates": 2,
            "passenger_load": "CRITICAL",
            "security_queue": "HIGH",
            "boarding_gates": 14,
        },
    },
}


class TerminalOperationsService:
    """Simulated terminal occupancy influenced by weather severity."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        severity_service: Optional[SeverityService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.severity_service = severity_service or get_severity_service()

    def get_terminal_operations(self, icao_code: Optional[str] = None) -> dict:
        assessment = self.severity_service.assess_current(icao_code)
        level = int(assessment.level.value)
        profile = _TERMINAL_BASELINES.get(level, _TERMINAL_BASELINES[1])

        # Shallow copy terminals for response safety
        data = {
            "terminal1": dict(profile["terminal1"]),
            "terminal2": dict(profile["terminal2"]),
            "terminal3": dict(profile["terminal3"]),
            "severity_level": level,
            "icao_code": (icao_code or self.settings.airport_icao).upper(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Terminal ops for %s (severity L%s): T3 load=%s",
            data["icao_code"],
            level,
            data["terminal3"]["passenger_load"],
        )
        return data


def get_terminal_operations_service() -> TerminalOperationsService:
    return TerminalOperationsService()
