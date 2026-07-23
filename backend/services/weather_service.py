"""Weather service — orchestrates the configured weather provider."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from backend.config import Settings, get_settings
from backend.models import WeatherObservation
from backend.weather import (
    MockWeatherProvider,
    TomorrowWeatherProvider,
    WeatherProvider,
    get_weather_provider,
)

logger = logging.getLogger(__name__)

# Keep weather/severity panels coherent when both endpoints are hit together.
_CACHE_TTL_SECONDS = 45.0
_weather_cache: dict[str, tuple[float, WeatherObservation]] = {}
_cache_lock = threading.Lock()


class TomorrowWeatherService:
    """Service wrapper for live Tomorrow.io weather (VIDP / Delhi IGI).

    Uses ``TomorrowWeatherProvider``, which falls back to mock on API failures.
    Frontend and route contracts remain unchanged.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.provider = TomorrowWeatherProvider(self.settings)
        logger.info("TomorrowWeatherService initialized (provider=TomorrowWeatherProvider)")

    def get_current_weather(self, icao_code: Optional[str] = None) -> WeatherObservation:
        """Fetch live weather from Tomorrow.io (with mock failover)."""
        code = (icao_code or self.settings.airport_icao).upper()
        logger.info("TomorrowWeatherService fetching weather for %s", code)
        return self.provider.get_current_weather(code)


class WeatherService:
    """Application service for airport weather retrieval."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        provider: Optional[WeatherProvider] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_weather_provider(self.settings)
        logger.info(
            "WeatherService using provider: %s (WEATHER_PROVIDER=%s)",
            type(self.provider).__name__,
            self.settings.weather_provider,
        )

    def get_current_weather(
        self,
        icao_code: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> WeatherObservation:
        """Fetch current weather for the given (or default) airport."""
        code = (icao_code or self.settings.airport_icao).upper()

        with _cache_lock:
            now = time.monotonic()
            if not force_refresh and code in _weather_cache:
                cached_at, cached_obs = _weather_cache[code]
                if now - cached_at < _CACHE_TTL_SECONDS:
                    logger.debug("Returning cached weather for %s", code)
                    return cached_obs

            logger.info(
                "Fetching weather for ICAO %s via %s",
                code,
                type(self.provider).__name__,
            )
            observation = self.provider.get_current_weather(code)
            _weather_cache[code] = (time.monotonic(), observation)
            return observation

    def get_airport_info(self) -> dict:
        """Return static airport metadata for the dashboard."""
        return {
            "icao_code": self.settings.airport_icao,
            "iata_code": self.settings.airport_iata,
            "name": self.settings.airport_name,
            "location": self.settings.airport_location,
            "timezone": "Asia/Kolkata",
            "elevation_ft": 777,
            "runways": ["09/27", "10/28", "11/29"],
        }


def get_weather_service() -> WeatherService:
    """FastAPI dependency factory for WeatherService."""
    return WeatherService()


__all__ = [
    "WeatherService",
    "TomorrowWeatherService",
    "MockWeatherProvider",
    "TomorrowWeatherProvider",
    "get_weather_service",
]
