"""Top-k retrieval over the AOCC knowledge vector store."""

from __future__ import annotations

import logging
from typing import Optional

from backend.config import Settings, get_settings
from backend.rag.vectorstore import ChromaVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """Retrieve the most relevant manual chunks for a question."""

    def __init__(
        self,
        vector_store: ChromaVectorStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.vector_store = vector_store or get_vector_store(self.settings)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[dict]:
        k = top_k or self.settings.rag_top_k
        threshold = self.settings.rag_min_score if min_score is None else min_score
        hits = self.vector_store.similarity_search(query, top_k=k)
        filtered = [hit for hit in hits if float(hit.get("score") or 0.0) >= threshold]
        logger.info(
            "Retrieved %s/%s chunk(s) for query=%r (min_score=%s)",
            len(filtered),
            len(hits),
            query[:80],
            threshold,
        )
        return filtered


def get_retriever(settings: Optional[Settings] = None) -> KnowledgeRetriever:
    return KnowledgeRetriever(settings=settings or get_settings())
