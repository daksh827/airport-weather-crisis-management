"""Chatbot and document upload API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.schemas import ChatRequest, success_response
from backend.services.assistant_service import AssistantService, get_assistant_service
from backend.services.rag_service import RAGService, get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chatbot"])


@router.post("/chat")
def chat(
    body: ChatRequest,
    assistant_service: AssistantService = Depends(get_assistant_service),
):
    """AOCC AI Assistant — answers from live operational data (Phase 7A)."""
    try:
        data = assistant_service.chat(body.message, session_id=body.session_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Chat handling failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return success_response(data, message="Chat response generated successfully")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(..., description="SOP or contingency document for future RAG"),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Upload a document for future RAG indexing (storage only until Phase 7B)."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    try:
        data = await rag_service.save_upload(file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return success_response(data, message="File uploaded successfully (RAG indexing pending)")
