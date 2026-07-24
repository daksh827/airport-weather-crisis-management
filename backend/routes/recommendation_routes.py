"""AI Operations Decision Support recommendation API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.schemas import success_response
from backend.services.recommendation_service import (
    RecommendationService,
    get_recommendation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recommendations"])


@router.get("/recommendations")
def get_recommendations(
    icao: Optional[str] = Query(default=None, description="Optional ICAO code"),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
):
    """Return rule-based AOCC operational recommendations for the current situation."""
    data = recommendation_service.get_recommendations(icao)
    return success_response(data, message="Operational recommendations generated successfully")
