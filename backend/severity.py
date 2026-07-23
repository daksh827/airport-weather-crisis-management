"""Airport Operational Severity Engine.

Classifies weather into Level 1 / 2 / 3 crisis bands for AOCC decision support.
Business thresholds live here so routes stay thin.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.models import SeverityAssessment, SeverityLevel, WeatherObservation

logger = logging.getLogger(__name__)


# Threshold reference (airport ops oriented — demo-tuned for VIDP)
# Airport operational thresholds (Delhi IGI)

VISIBILITY_LEVEL3_M = 550
VISIBILITY_LEVEL2_M = 1200

WIND_LEVEL3_KT = 40
WIND_LEVEL2_KT = 28

RAIN_LEVEL3_MM = 40
RAIN_LEVEL2_MM = 15


LEVEL_DEFINITIONS: dict[SeverityLevel, dict[str, str]] = {
    SeverityLevel.LEVEL_1: {
        "color": "#22c55e",
        "title": "Level 1 - Normal Operations",
        "description": (
            "Weather conditions are within normal operating parameters. "
            "No significant impact on runway throughput or ground movement is expected."
        ),
        "operational_guidance": (
            "Maintain standard AOCC monitoring cadence. Continue routine runway "
            "inspections and publish normal ATIS / NOTAM status."
        ),
        "recommended_action": (
            "No special measures required. Keep weather watch active and brief "
            "next shift on current trends."
        ),
    },
    SeverityLevel.LEVEL_2: {
        "color": "#f59e0b",
        "title": "Level 2 - Elevated Caution",
        "description": (
            "Degraded weather may reduce arrival/departure rates. Visibility, wind, "
            "or rainfall is approaching operational limits."
        ),
        "operational_guidance": (
            "Activate heightened monitoring. Coordinate with ATC and apron control "
            "on possible flow restrictions. Prepare Low Visibility Procedures (LVP) "
            "standby teams if visibility continues to fall."
        ),
        "recommended_action": (
            "Brief airlines on potential delays. Review diversion contingency slots. "
            "Increase runway friction and lighting checks."
        ),
    },
    SeverityLevel.LEVEL_3: {
        "color": "#ef4444",
        "title": "Level 3 - Crisis / Severe Impact",
        "description": (
            "Severe weather is likely to disrupt airport operations. Expect significant "
            "capacity reduction, holding, diversions, or temporary runway closures."
        ),
        "operational_guidance": (
            "Convene AOCC crisis cell. Implement LVP / severe weather protocols. "
            "Coordinate with ATC for ground stops or arrival metering. Prioritize "
            "safety-critical movements and passenger welfare messaging."
        ),
        "recommended_action": (
            "Declare operational alert to airlines and ground handlers. Open "
            "diversion coordination channel. Update passengers via airport "
            "communication channels and prepare recovery sequencing."
        ),
    },
}


def _evaluate_factors(weather: WeatherObservation) -> tuple[SeverityLevel, list[str]]:
    """Score weather against operational thresholds and collect factors."""
    factors: list[str] = []
    score = 1

    if weather.visibility <= VISIBILITY_LEVEL3_M:
        score = max(score, 3)
        factors.append(f"Critical visibility ({weather.visibility:.0f} m)")
    elif weather.visibility <= VISIBILITY_LEVEL2_M:
        score = max(score, 2)
        factors.append(f"Reduced visibility ({weather.visibility:.0f} m)")

    if weather.wind_speed >= WIND_LEVEL3_KT:
        score = max(score, 3)
        factors.append(f"Gale / severe wind ({weather.wind_speed:.1f} kt)")
    elif weather.wind_speed >= WIND_LEVEL2_KT:
        score = max(score, 2)
        factors.append(f"Strong wind ({weather.wind_speed:.1f} kt)")

    if weather.rainfall >= RAIN_LEVEL3_MM:
        score = max(score, 3)
        factors.append(f"Heavy rainfall ({weather.rainfall:.1f} mm)")
    elif weather.rainfall >= RAIN_LEVEL2_MM:
        score = max(score, 2)
        factors.append(f"Moderate rainfall ({weather.rainfall:.1f} mm)")

    description = (weather.weather_description or "").lower()
    if any(token in description for token in ("thunderstorm", "gale", "severe")):
        score = max(score, 3)
        factors.append(f"Hazardous weather: {weather.weather_description}")
    elif "thunderstorm" in description:
        score = max(score, 3)
        factors.append("Thunderstorm reported")
    elif "fog" in description:
        score = max(score, 2)
        factors.append("Fog reported")
    elif "mist" in description:
        score = max(score, 2)
        factors.append("Mist reported")

        if "weather description" not in " ".join(factors).lower():
            factors.append(f"Adverse weather: {weather.weather_description}")

    if not factors:
        factors.append("All primary weather parameters within normal limits")

    return SeverityLevel(score), factors


def assess_severity(weather: WeatherObservation) -> SeverityAssessment:
    """Produce a full severity assessment from a weather observation."""
    level, factors = _evaluate_factors(weather)
    definition = LEVEL_DEFINITIONS[level]
    assessed_at = datetime.now(timezone.utc)

    assessment = SeverityAssessment(
        level=level,
        color=definition["color"],
        title=definition["title"],
        description=definition["description"],
        operational_guidance=definition["operational_guidance"],
        recommended_action=definition["recommended_action"],
        icao_code=weather.icao_code,
        assessed_at=assessed_at,
        contributing_factors=factors,
    )
    logger.info(
        "Severity assessed for %s → Level %s (%s)",
        weather.icao_code,
        level.value,
        ", ".join(factors),
    )
    return assessment


def get_level_definition(level: SeverityLevel) -> dict[str, str]:
    """Return static metadata for a severity level."""
    return LEVEL_DEFINITIONS[level]
