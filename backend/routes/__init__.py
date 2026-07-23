"""API route modules for weather, severity, and chatbot endpoints."""

from fastapi import APIRouter

from backend.routes.chatbot_routes import router as chatbot_router
from backend.routes.severity_routes import router as severity_router
from backend.routes.weather_routes import router as weather_router

api_router = APIRouter(prefix="/api")
api_router.include_router(weather_router)
api_router.include_router(severity_router)
api_router.include_router(chatbot_router)

__all__ = ["api_router", "weather_router", "severity_router", "chatbot_router"]
