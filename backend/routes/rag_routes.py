"""RAG status and reindex API routes (Phase 7B)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.rag.rag_service import KnowledgeRAGService, get_knowledge_rag_service
from backend.schemas import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.get("/status")
def rag_status(
    rag_service: KnowledgeRAGService = Depends(get_knowledge_rag_service),
):
    """Return knowledge-base indexing status."""
    data = rag_service.get_status()
    return success_response(data, message="RAG status retrieved successfully")


@router.post("/reindex")
def rag_reindex(
    rag_service: KnowledgeRAGService = Depends(get_knowledge_rag_service),
):
    """Delete the vector database and rebuild from backend/knowledge_base."""
    try:
        data = rag_service.reindex()
    except Exception as exc:
        logger.exception("RAG reindex failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return success_response(data, message="Knowledge base reindexed successfully")
