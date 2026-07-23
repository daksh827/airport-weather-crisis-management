"""Severity API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import success_response
from backend.services.severity_service import SeverityService, get_severity_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Severity"])


@router.get("/severity")
def get_severity(
    icao: Optional[str] = Query(
        default=None,
        description="Optional ICAO code (defaults to configured airport, VIDP)",
    ),
    severity_service: SeverityService = Depends(get_severity_service),
):
    """Return airport operational severity assessment."""
    assessment = severity_service.assess_current(icao)
    payload = {
        "level": int(assessment.level.value),
        "color": assessment.color,
        "title": assessment.title,
        "description": assessment.description,
        "operational_guidance": assessment.operational_guidance,
        "recommended_action": assessment.recommended_action,
        "icao_code": assessment.icao_code,
        "assessed_at": assessment.assessed_at.isoformat(),
        "contributing_factors": assessment.contributing_factors,
    }
    return success_response(payload, message="Severity assessment completed successfully")
