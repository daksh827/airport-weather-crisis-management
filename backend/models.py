"""Domain models used across weather, severity, and chat services."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SeverityLevel(int, Enum):
    """Airport operational crisis severity levels."""

    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class WeatherObservation(BaseModel):
    """Normalized weather observation for a single airport."""

    icao_code: str = Field(..., description="ICAO airport code")
    airport_name: str
    location: str
    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: float = Field(..., description="Relative humidity percentage")
    pressure: float = Field(..., description="Atmospheric pressure in hPa")
    visibility: float = Field(..., description="Visibility in meters")
    wind_speed: float = Field(..., description="Wind speed in knots")
    wind_direction: str = Field(..., description="Wind direction (e.g. NW, 270°)")
    rainfall: float = Field(..., description="Rainfall in mm")
    weather_description: str
    observation_time: datetime
    last_updated: datetime
    timestamp: datetime
    source: str = "mock"


class SeverityAssessment(BaseModel):
    """Operational severity assessment derived from weather conditions."""

    level: SeverityLevel
    color: str
    title: str
    description: str
    operational_guidance: str
    recommended_action: str
    icao_code: str
    assessed_at: datetime
    contributing_factors: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """Single chat turn between operator and AOCC AI assistant."""

    role: str = Field(..., description="user | assistant | system")
    content: str
    timestamp: Optional[datetime] = None


class ChatResponse(BaseModel):
    """Chatbot reply payload."""

    reply: str
    provider: str = "mock"
    context_used: bool = False
    timestamp: datetime
