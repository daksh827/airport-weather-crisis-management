"""Embedding providers for AOCC RAG (Gemini first, MiniLM fallback)."""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Common embedding interface used by the vector store."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Generative AI embeddings compatible with Gemini."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "models/text-embedding-004",
    ) -> None:
        import google.generativeai as genai

        self._genai = genai
        self._genai.configure(api_key=api_key)
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        import time

        vectors: list[list[float]] = []
        for index, text in enumerate(texts):
            result = self._genai.embed_content(
                model=self._model_name,
                content=text,
                task_type="retrieval_document",
            )
            embedding = result.get("embedding")
            if not embedding:
                raise RuntimeError("Gemini embedding response missing 'embedding'")
            vectors.append(list(embedding))
            # Soft pacing to reduce free-tier rate-limit pressure
            if index + 1 < len(texts):
                time.sleep(0.05)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        result = self._genai.embed_content(
            model=self._model_name,
            content=text,
            task_type="retrieval_query",
        )
        embedding = result.get("embedding")
        if not embedding:
            raise RuntimeError("Gemini embedding response missing 'embedding'")
        return list(embedding)


class MiniLMEmbeddingProvider(EmbeddingProvider):
    """Local Sentence-Transformers fallback: all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()


_provider: Optional[EmbeddingProvider] = None
_provider_lock = threading.Lock()


def get_embedding_provider(settings: Optional[Settings] = None) -> EmbeddingProvider:
    """Return a process-wide embedding provider (Gemini preferred)."""
    global _provider
    if _provider is not None:
        return _provider

    with _provider_lock:
        if _provider is not None:
            return _provider

        cfg = settings or get_settings()
        api_key = (cfg.gemini_api_key or "").strip()
        candidates = [
            cfg.gemini_embedding_model,
            "models/gemini-embedding-001",
            "models/embedding-001",
            "models/text-embedding-004",
        ]
        # Preserve order while removing duplicates
        seen: set[str] = set()
        unique_candidates = []
        for name in candidates:
            if name and name not in seen:
                seen.add(name)
                unique_candidates.append(name)

        if api_key:
            last_error: Exception | None = None
            for model_name in unique_candidates:
                try:
                    provider = GeminiEmbeddingProvider(
                        api_key=api_key,
                        model_name=model_name,
                    )
                    provider.embed_query("AOCC embedding probe")
                    _provider = provider
                    logger.info("Using Gemini embeddings: %s", provider.model_name)
                    return _provider
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Gemini embedding model %s unavailable (%s)",
                        model_name,
                        exc,
                    )
            logger.warning(
                "All Gemini embedding models failed (%s); trying MiniLM fallback",
                last_error,
            )

        try:
            _provider = MiniLMEmbeddingProvider("all-MiniLM-L6-v2")
            logger.info("Using Sentence-Transformers embeddings: %s", _provider.model_name)
            return _provider
        except Exception as exc:
            raise RuntimeError(
                "No embedding provider available. Configure GEMINI_API_KEY or "
                "install sentence-transformers."
            ) from exc
