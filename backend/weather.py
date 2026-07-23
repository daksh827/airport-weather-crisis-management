"""Weather provider abstractions: mock and Tomorrow.io.

Architecture
------------
``WeatherProvider`` is the contract every weather source must implement.
``get_weather_provider`` selects Mock or Tomorrow based on ``WEATHER_PROVIDER``.
Tomorrow.io failures automatically fall back to the mock provider.
"""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from backend.config import Settings, get_settings
from backend.models import WeatherObservation

logger = logging.getLogger(__name__)

# Delhi IGI (VIDP) — used when ICAO lookup is unsupported by Tomorrow.io
VIDP_LATITUDE = 28.5562
VIDP_LONGITUDE = 77.1000
TOMORROW_REALTIME_URL = "https://api.tomorrow.io/v4/weather/realtime"
TOMORROW_TIMEOUT_SECONDS = 10.0

# Tomorrow.io weatherCode → human-readable description
WEATHER_CODE_DESCRIPTIONS: dict[int, str] = {
    0: "Unknown",
    1000: "Clear",
    1100: "Mostly clear",
    1101: "Partly cloudy",
    1102: "Mostly cloudy",
    1001: "Cloudy",
    2000: "Fog",
    2100: "Light fog",
    4000: "Drizzle",
    4001: "Rain",
    4200: "Light rain",
    4201: "Heavy rain",
    5000: "Snow",
    5001: "Flurries",
    5100: "Light snow",
    5101: "Heavy snow",
    6000: "Freezing drizzle",
    6001: "Freezing rain",
    6200: "Light freezing rain",
    6201: "Heavy freezing rain",
    7000: "Ice pellets",
    7101: "Heavy ice pellets",
    7102: "Light ice pellets",
    8000: "Thunderstorm",
}


class WeatherProvider(ABC):
    """Abstract weather data provider."""

    @abstractmethod
    def get_current_weather(self, icao_code: Optional[str] = None) -> WeatherObservation:
        """Return the current weather observation for an airport."""


class MockWeatherProvider(WeatherProvider):
    """Deterministic-leaning mock weather for Delhi IGI Airport (VIDP)."""

    _SCENARIOS = (
        {
            "weight": 4,
            "temperature": 28.0,
            "humidity": 55.0,
            "pressure": 1012.0,
            "visibility": 8000.0,
            "wind_speed": 8.0,
            "wind_direction": "NW",
            "rainfall": 0.0,
            "weather_description": "Partly cloudy",
        },
        {
            "weight": 3,
            "temperature": 24.0,
            "humidity": 78.0,
            "pressure": 1006.0,
            "visibility": 3500.0,
            "wind_speed": 18.0,
            "wind_direction": "SE",
            "rainfall": 4.5,
            "weather_description": "Moderate rain showers",
        },
        {
            "weight": 2,
            "temperature": 21.0,
            "humidity": 92.0,
            "pressure": 998.0,
            "visibility": 900.0,
            "wind_speed": 32.0,
            "wind_direction": "E",
            "rainfall": 22.0,
            "weather_description": "Heavy rain with reduced visibility",
        },
        {
            "weight": 1,
            "temperature": 19.0,
            "humidity": 96.0,
            "pressure": 992.0,
            "visibility": 400.0,
            "wind_speed": 42.0,
            "wind_direction": "ENE",
            "rainfall": 38.0,
            "weather_description": "Thunderstorm with gale-force winds",
        },
    )

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._last_scenario: Optional[dict] = None

    def _pick_scenario(self) -> dict:
        population = self._SCENARIOS
        weights = [s["weight"] for s in population]
        chosen = random.choices(population, weights=weights, k=1)[0]
        jittered = {
            **chosen,
            "temperature": round(chosen["temperature"] + random.uniform(-1.2, 1.2), 1),
            "humidity": round(min(100.0, max(5.0, chosen["humidity"] + random.uniform(-3, 3))), 1),
            "pressure": round(chosen["pressure"] + random.uniform(-2, 2), 1),
            "visibility": round(max(100.0, chosen["visibility"] + random.uniform(-150, 150)), 0),
            "wind_speed": round(max(0.0, chosen["wind_speed"] + random.uniform(-2, 2)), 1),
            "rainfall": round(max(0.0, chosen["rainfall"] + random.uniform(-1, 1)), 1),
        }
        self._last_scenario = jittered
        return jittered

    def get_current_weather(self, icao_code: Optional[str] = None) -> WeatherObservation:
        code = (icao_code or self.settings.airport_icao).upper()
        now = datetime.now(timezone.utc)
        scenario = self._pick_scenario()

        observation = WeatherObservation(
            icao_code=code,
            airport_name=self.settings.airport_name,
            location=self.settings.airport_location,
            temperature=scenario["temperature"],
            humidity=scenario["humidity"],
            pressure=scenario["pressure"],
            visibility=scenario["visibility"],
            wind_speed=scenario["wind_speed"],
            wind_direction=scenario["wind_direction"],
            rainfall=scenario["rainfall"],
            weather_description=scenario["weather_description"],
            observation_time=now,
            last_updated=now,
            timestamp=now,
            source="mock",
        )
        logger.debug("Mock weather generated for %s: %s", code, observation.weather_description)
        return observation


def _degrees_to_compass(degrees: float) -> str:
    """Convert wind direction degrees to a 16-point compass label."""
    directions = (
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    )
    normalized = degrees % 360
    index = int((normalized + 11.25) // 22.5) % 16
    return f"{directions[index]} ({normalized:.0f}°)"


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_observation_time(raw: Any) -> datetime:
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def map_tomorrow_payload(
    payload: dict[str, Any],
    *,
    icao_code: str,
    airport_name: str,
    location: str,
) -> WeatherObservation:
    """Map Tomorrow.io realtime JSON into the existing WeatherObservation model."""
    data = payload.get("data") or {}
    values = data.get("values") or {}
    if not isinstance(values, dict) or not values:
        raise ValueError("Tomorrow.io response missing data.values")

    now = datetime.now(timezone.utc)
    observation_time = _parse_observation_time(data.get("time"))

    # Metric units: visibility is km → meters; windSpeed is m/s → knots
    visibility_km = _safe_float(values.get("visibility"), 10.0)
    wind_mps = _safe_float(values.get("windSpeed"), 0.0)
    wind_deg = _safe_float(values.get("windDirection"), 0.0)

    pressure = _safe_float(
        values.get("pressureSeaLevel", values.get("pressureSurfaceLevel")),
        1013.25,
    )
    rainfall = _safe_float(
        values.get("rainIntensity", values.get("precipitationIntensity")),
        0.0,
    )
    weather_code = int(_safe_float(values.get("weatherCode"), 0))
    description = WEATHER_CODE_DESCRIPTIONS.get(weather_code, f"Weather code {weather_code}")

    return WeatherObservation(
        icao_code=icao_code,
        airport_name=airport_name,
        location=location,
        temperature=round(_safe_float(values.get("temperature"), 25.0), 1),
        humidity=round(_safe_float(values.get("humidity"), 50.0), 1),
        pressure=round(pressure, 1),
        visibility=round(max(0.0, visibility_km * 1000.0), 0),
        wind_speed=round(max(0.0, wind_mps * 1.94384), 1),
        wind_direction=_degrees_to_compass(wind_deg),
        rainfall=round(max(0.0, rainfall), 1),
        weather_description=description,
        observation_time=observation_time,
        last_updated=now,
        timestamp=now,
        source="tomorrow.io",
    )


class TomorrowWeatherProvider(WeatherProvider):
    """Live weather from Tomorrow.io Realtime API for VIDP (Delhi IGI)."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._fallback = MockWeatherProvider(self.settings)

    def get_current_weather(self, icao_code: Optional[str] = None) -> WeatherObservation:
        code = (icao_code or self.settings.airport_icao).upper()
        api_key = (self.settings.weather_api_key or "").strip()

        if not api_key:
            logger.error(
                "Fallback reason: WEATHER_API_KEY is missing; using mock provider"
            )
            return self._fallback.get_current_weather(code)

        location = f"{VIDP_LATITUDE},{VIDP_LONGITUDE}"
        params = {
            "location": location,
            "apikey": api_key,
            "units": "metric",
        }

        logger.info(
            "Tomorrow.io request: GET %s location=%s icao=%s",
            TOMORROW_REALTIME_URL,
            location,
            code,
        )

        try:
            with httpx.Client(timeout=TOMORROW_TIMEOUT_SECONDS) as client:
                response = client.get(TOMORROW_REALTIME_URL, params=params)

            logger.info("Tomorrow.io response status: %s", response.status_code)

            if response.status_code != 200:
                logger.error(
                    "Fallback reason: Tomorrow.io HTTP %s — %s",
                    response.status_code,
                    response.text[:300],
                )
                return self._fallback.get_current_weather(code)

            payload = response.json()
            observation = map_tomorrow_payload(
                payload,
                icao_code=code,
                airport_name=self.settings.airport_name,
                location=self.settings.airport_location,
            )
            logger.info(
                "Tomorrow.io weather for %s: %s (temp=%s°C, vis=%sm)",
                code,
                observation.weather_description,
                observation.temperature,
                observation.visibility,
            )
            return observation

        except httpx.TimeoutException as exc:
            logger.error("Fallback reason: Tomorrow.io timeout — %s", exc)
            return self._fallback.get_current_weather(code)
        except httpx.HTTPError as exc:
            logger.error("Fallback reason: Tomorrow.io HTTP error — %s", exc)
            return self._fallback.get_current_weather(code)
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("Fallback reason: invalid Tomorrow.io data — %s", exc)
            return self._fallback.get_current_weather(code)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Fallback reason: unexpected Tomorrow.io failure — %s", exc)
            return self._fallback.get_current_weather(code)


# Backward-compatible alias used by earlier stubs
TomorrowIOWeatherProvider = TomorrowWeatherProvider


def get_weather_provider(settings: Optional[Settings] = None) -> WeatherProvider:
    """Factory that returns the configured weather provider instance."""
    cfg = settings or get_settings()
    provider_name = (cfg.weather_provider or "mock").strip().lower()

    if provider_name in {"tomorrow", "tomorrow_io", "tomorrow.io"}:
        logger.info("Current weather provider: TomorrowWeatherProvider")
        return TomorrowWeatherProvider(cfg)

    logger.info("Current weather provider: MockWeatherProvider")
    return MockWeatherProvider(cfg)
