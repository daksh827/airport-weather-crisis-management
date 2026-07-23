"""Weather API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import APIResponse, WeatherData, success_response
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Weather"])


@router.get("/weather", response_model=APIResponse[WeatherData])
def get_weather(
    icao: Optional[str] = Query(
        default=None,
        description="Optional ICAO code (defaults to configured airport, VIDP)",
    ),
    weather_service: WeatherService = Depends(get_weather_service),
):
    """Return current airport weather observation."""
    observation = weather_service.get_current_weather(icao)
    payload = {
        "icao_code": observation.icao_code,
        "airport_name": observation.airport_name,
        "location": observation.location,
        "temperature": observation.temperature,
        "humidity": observation.humidity,
        "pressure": observation.pressure,
        "visibility": observation.visibility,
        "wind_speed": observation.wind_speed,
        "wind_direction": observation.wind_direction,
        "rainfall": observation.rainfall,
        "weather_description": observation.weather_description,
        "observation_time": observation.observation_time.isoformat(),
        "last_updated": observation.last_updated.isoformat(),
        "timestamp": observation.timestamp.isoformat(),
        "source": observation.source,
    }
    return success_response(payload, message="Weather data retrieved successfully")
