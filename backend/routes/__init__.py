"""API route modules for weather, severity, chatbot, alerts, and operations."""

from fastapi import APIRouter

from backend.routes.alert_routes import router as alert_router
from backend.routes.chatbot_routes import router as chatbot_router
from backend.routes.operations_routes import notifications_router, operations_router
from backend.routes.severity_routes import router as severity_router
from backend.routes.weather_routes import router as weather_router

api_router = APIRouter(prefix="/api")
api_router.include_router(weather_router)
api_router.include_router(severity_router)
api_router.include_router(chatbot_router)
api_router.include_router(alert_router)
api_router.include_router(operations_router)
api_router.include_router(notifications_router)

__all__ = [
    "api_router",
    "weather_router",
    "severity_router",
    "chatbot_router",
    "alert_router",
    "operations_router",
    "notifications_router",
]
