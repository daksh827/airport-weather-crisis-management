"""Operations impact, flights, runway, terminal, ground, KPI, and notification API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import success_response
from backend.services.flight_service import FlightOperationsService, get_flight_operations_service
from backend.services.ground_service import GroundOperationsService, get_ground_operations_service
from backend.services.impact_service import ImpactService, get_impact_service
from backend.services.kpi_service import AirportKPIService, get_airport_kpi_service
from backend.services.notification_service import NotificationService, get_notification_service
from backend.services.runway_service import RunwayOperationsService, get_runway_operations_service
from backend.services.terminal_service import TerminalOperationsService, get_terminal_operations_service

logger = logging.getLogger(__name__)

operations_router = APIRouter(prefix="/operations", tags=["Operations"])
notifications_router = APIRouter(tags=["Notifications"])


@operations_router.get("/impact")
def get_operations_impact(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    impact_service: ImpactService = Depends(get_impact_service),
):
    """Return AOCC operational impact assessment from live weather."""
    data = impact_service.get_impact(icao)
    return success_response(data, message="Operational impact assessed successfully")


@operations_router.get("/flights")
def get_flight_operations(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    flight_service: FlightOperationsService = Depends(get_flight_operations_service),
):
    """Return simulated daily flight operations summary for AOCC."""
    data = flight_service.get_flight_operations(icao)
    return success_response(data, message="Flight operations retrieved successfully")


@operations_router.get("/runway")
def get_runway_operations(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    runway_service: RunwayOperationsService = Depends(get_runway_operations_service),
):
    """Return runway status influenced by current weather severity."""
    data = runway_service.get_runway_operations(icao)
    return success_response(data, message="Runway operations retrieved successfully")


@operations_router.get("/terminal")
def get_terminal_operations(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    terminal_service: TerminalOperationsService = Depends(get_terminal_operations_service),
):
    """Return Terminal 1/2/3 operations summary."""
    data = terminal_service.get_terminal_operations(icao)
    return success_response(data, message="Terminal operations retrieved successfully")


@operations_router.get("/ground")
def get_ground_operations(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    ground_service: GroundOperationsService = Depends(get_ground_operations_service),
):
    """Return ground support vehicle fleet status."""
    data = ground_service.get_ground_operations(icao)
    return success_response(data, message="Ground operations retrieved successfully")


@operations_router.get("/kpi")
def get_airport_kpis(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    kpi_service: AirportKPIService = Depends(get_airport_kpi_service),
):
    """Return airport KPI dashboard metrics."""
    data = kpi_service.get_kpis(icao)
    return success_response(data, message="Airport KPIs retrieved successfully")


@notifications_router.get("/notifications")
def get_notifications(
    limit: int = Query(default=30, ge=1, le=80),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Return AOCC notification timeline (newest first)."""
    data = {"items": notification_service.list_events(limit=limit)}
    return success_response(data, message="Notifications retrieved successfully")
