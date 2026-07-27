"""Incident Management API routes (Phase 6A–6C)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from backend.schemas import success_response
from backend.schemas.incident import CreateIncidentRequest, UpdateIncidentRequest
from backend.services.incident_service import IncidentService, get_incident_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("/stats")
def get_incident_stats(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Return live incident statistics for dashboard cards."""
    data = incident_service.get_stats(icao)
    return success_response(data, message="Incident statistics retrieved successfully")


@router.get("/history")
def get_incident_history(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Return resolved and closed incident history."""
    data = incident_service.get_history(icao)
    return success_response(data, message="Incident history retrieved successfully")


@router.get("/export")
def export_incident_history(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Download incident history as CSV."""
    filename, csv_text = incident_service.export_history_csv(icao)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/timeline/{incident_id}")
def get_incident_timeline(
    incident_id: str,
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Return timeline events for a single incident."""
    try:
        data = incident_service.get_timeline(incident_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success_response(data, message="Incident timeline retrieved successfully")


@router.get("")
def list_incidents(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    search: Optional[str] = Query(default=None, description="Search text"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    department: Optional[str] = Query(default=None, description="Filter by department"),
    incident_type: Optional[str] = Query(
        default=None, description="Filter by incident type"
    ),
    sort: Optional[str] = Query(
        default=None,
        description="Sort: newest, oldest, highest_severity, lowest_severity, status, created_time",
    ),
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Return AOCC incident records for the dashboard table."""
    data = incident_service.list_incidents(
        icao,
        search=search,
        severity=severity,
        status=status_filter,
        department=department,
        incident_type=incident_type,
        sort=sort,
    )
    return success_response(data, message="Incidents retrieved successfully")


@router.post("")
def create_incident(
    body: CreateIncidentRequest,
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Create a new incident with auto department assignment."""
    try:
        data = incident_service.create_incident(
            incident_type=body.incident_type,
            description=body.description,
            severity=body.severity,
            airport_area=body.airport_area,
            icao_code=body.icao_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return success_response(data, message="Incident created successfully")


@router.put("/{incident_id}")
def update_incident(
    incident_id: str,
    body: UpdateIncidentRequest,
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Update incident status, description, and/or airport area."""
    try:
        data = incident_service.update_incident(
            incident_id,
            status=body.status,
            description=body.description,
            airport_area=body.airport_area,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return success_response(data, message="Incident updated successfully")


@router.delete("/{incident_id}")
def delete_incident(
    incident_id: str,
    incident_service: IncidentService = Depends(get_incident_service),
):
    """Delete an incident from the in-memory store."""
    try:
        data = incident_service.delete_incident(incident_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return success_response(data, message="Incident deleted successfully")
