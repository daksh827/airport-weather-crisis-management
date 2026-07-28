"""AOCC RAG package (Phase 7B) — load, embed, retrieve, and generate.

Also preserves the Phase-1 ``RAGProvider`` contract used by upload storage.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from backend.config import DOCUMENTS_DIR, UPLOADS_DIR, VECTORSTORE_DIR, Settings, get_settings
from backend.rag.rag_service import KnowledgeRAGService, get_knowledge_rag_service

logger = logging.getLogger(__name__)


class RAGProvider(ABC):
    """Abstract RAG interface retained for upload / legacy callers."""

    @abstractmethod
    def is_ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def ingest_file(self, file_path: Path) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError


class ChromaBackedRAGProvider(RAGProvider):
    """Adapter that exposes KnowledgeRAGService through the legacy interface."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.documents_dir = DOCUMENTS_DIR
        self.uploads_dir = UPLOADS_DIR
        self.vectorstore_dir = VECTORSTORE_DIR
        for path in (self.documents_dir, self.uploads_dir, self.vectorstore_dir):
            path.mkdir(parents=True, exist_ok=True)
        self._rag = get_knowledge_rag_service(self.settings)

    def is_ready(self) -> bool:
        return bool(self._rag.get_status().get("indexed"))

    def ingest_file(self, file_path: Path) -> dict:
        """Acknowledge uploads; knowledge_base reindex remains the source of truth."""
        logger.info("Upload acknowledged for future knowledge use: %s", file_path.name)
        return {
            "filename": file_path.name,
            "indexed": False,
            "status": "stored",
            "message": (
                "File stored. AOCC knowledge indexing uses backend/knowledge_base/. "
                "Call POST /api/rag/reindex after adding SOP manuals there."
            ),
        }

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        return self._rag.retrieve(query, top_k=top_k)


def get_rag_provider(settings: Optional[Settings] = None) -> RAGProvider:
    return ChromaBackedRAGProvider(settings)


__all__ = [
    "RAGProvider",
    "ChromaBackedRAGProvider",
    "get_rag_provider",
    "KnowledgeRAGService",
    "get_knowledge_rag_service",
]
