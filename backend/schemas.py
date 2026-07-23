"""API request/response schemas with a uniform envelope."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response envelope used by every endpoint."""

    success: bool = True
    message: str = "Success"
    data: Optional[T] = None


class HealthData(BaseModel):
    """Health check payload."""

    status: str = "healthy"
    app_name: str
    version: str
    timestamp: datetime
    weather_provider: str
    chat_provider: str


class WeatherData(BaseModel):
    """Weather API data block."""

    icao_code: str
    airport_name: str
    location: str
    temperature: float
    humidity: float
    pressure: float
    visibility: float
    wind_speed: float
    wind_direction: str
    rainfall: float
    weather_description: str
    observation_time: datetime
    last_updated: datetime
    timestamp: datetime
    source: str


class SeverityData(BaseModel):
    """Severity API data block."""

    level: int
    color: str
    title: str
    description: str
    operational_guidance: str
    recommended_action: str
    icao_code: str
    assessed_at: datetime
    contributing_factors: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Incoming chat request from the AOCC dashboard."""

    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None


class ChatData(BaseModel):
    """Chat API data block."""

    reply: str
    provider: str
    context_used: bool
    timestamp: datetime
    session_id: Optional[str] = None


class UploadData(BaseModel):
    """Document upload acknowledgment (RAG placeholder)."""

    filename: str
    saved_as: str
    size_bytes: int
    content_type: Optional[str] = None
    status: str = "stored"
    rag_indexed: bool = False
    note: str = "Stored for future RAG indexing. Embeddings are not generated yet."


class AirportInfoData(BaseModel):
    """Static airport information for the dashboard."""

    icao_code: str
    iata_code: str
    name: str
    location: str
    timezone: str = "Asia/Kolkata"
    elevation_ft: int = 777
    runways: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    """Structured error detail for exception handlers."""

    detail: str
    error_code: Optional[str] = None
    extras: dict[str, Any] = Field(default_factory=dict)


def success_response(data: Any = None, message: str = "Success") -> dict[str, Any]:
    """Build a uniform success envelope as a plain dict."""
    return {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }


def error_response(
    message: str,
    data: Any = None,
    *,
    success: bool = False,
) -> dict[str, Any]:
    """Build a uniform error envelope as a plain dict."""
    return {
        "success": success,
        "message": message,
        "data": data if data is not None else {},
    }


# Re-export for convenience in routes
__all__ = [
    "APIResponse",
    "HealthData",
    "WeatherData",
    "SeverityData",
    "ChatRequest",
    "ChatData",
    "UploadData",
    "AirportInfoData",
    "ErrorDetail",
    "success_response",
    "error_response",
]
