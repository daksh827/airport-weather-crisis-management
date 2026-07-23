"""RAG (Retrieval-Augmented Generation) architecture placeholders.

Future implementation plan
--------------------------
1. Ingest SOP / contingency PDFs from ``documents/`` and ``uploads/``.
2. Chunk text and embed with Sentence Transformers.
3. Persist vectors in FAISS under ``vectorstore/``.
4. Retrieve top-k passages and pass them to LangChain + Google Gemini.

This module intentionally contains NO embeddings, FAISS indexing, or LLM calls.
It only defines the contract and stub methods so the rest of the system can
depend on a stable interface.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from backend.config import DOCUMENTS_DIR, UPLOADS_DIR, VECTORSTORE_DIR, Settings, get_settings

logger = logging.getLogger(__name__)


class RAGProvider(ABC):
    """Abstract RAG interface for future document search."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True when the vector index is available."""

    @abstractmethod
    def ingest_file(self, file_path: Path) -> dict:
        """Ingest a document into the future vector store."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search indexed documents (placeholder)."""


class PlaceholderRAGProvider(RAGProvider):
    """No-op RAG provider used until LangChain + FAISS + Gemini are wired."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.documents_dir = DOCUMENTS_DIR
        self.uploads_dir = UPLOADS_DIR
        self.vectorstore_dir = VECTORSTORE_DIR
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for path in (self.documents_dir, self.uploads_dir, self.vectorstore_dir):
            path.mkdir(parents=True, exist_ok=True)

    def is_ready(self) -> bool:
        # Always False until real indexing is implemented
        return False

    def ingest_file(self, file_path: Path) -> dict:
        """Acknowledge a file for future indexing without creating embeddings."""
        logger.info("RAG placeholder ingest acknowledged: %s", file_path.name)
        return {
            "filename": file_path.name,
            "indexed": False,
            "status": "pending_rag_implementation",
            "message": (
                "File stored. Embedding / FAISS indexing will be enabled in a "
                "future release (LangChain + Sentence Transformers + Gemini)."
            ),
        }

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return an empty result set — real retrieval not implemented yet."""
        logger.debug("RAG placeholder search called (query=%r, top_k=%s)", query, top_k)
        return []


def get_rag_provider(settings: Optional[Settings] = None) -> RAGProvider:
    """Factory for the configured RAG provider (placeholder only for now)."""
    return PlaceholderRAGProvider(settings)
