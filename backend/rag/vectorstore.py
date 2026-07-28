"""ChromaDB persistence layer for AOCC RAG (Phase 7B)."""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from pathlib import Path
from typing import Optional, Sequence

from backend.config import VECTOR_DB_DIR, Settings, get_settings
from backend.rag.embeddings import EmbeddingProvider, get_embedding_provider
from backend.rag.loader import DocumentChunkSource

logger = logging.getLogger(__name__)

_store_lock = threading.Lock()
_store: Optional["ChromaVectorStore"] = None


class ChromaVectorStore:
    """Persistent Chroma collection for AOCC knowledge chunks."""

    def __init__(
        self,
        *,
        persist_dir: Path | None = None,
        collection_name: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.settings = settings or get_settings()
        self.persist_dir = Path(persist_dir or VECTOR_DB_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name or self.settings.rag_collection_name
        self.embedding_provider = embedding_provider or get_embedding_provider(self.settings)

        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Chroma vector store ready at %s (collection=%s, count=%s)",
            self.persist_dir,
            self.collection_name,
            self.count(),
        )

    @property
    def embedding_model(self) -> str:
        return self.embedding_provider.model_name

    def count(self) -> int:
        return int(self._collection.count())

    def is_indexed(self) -> bool:
        return self.count() > 0

    def add_documents(self, chunks: Sequence[DocumentChunkSource]) -> int:
        if not chunks:
            return 0

        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embedding_provider.embed_documents(texts)
        ids = [f"chunk_{uuid.uuid4().hex}" for _ in chunks]
        metadatas = []
        for chunk in chunks:
            meta = {
                key: ("" if value is None else str(value))
                for key, value in chunk.metadata.items()
            }
            metadatas.append(meta)

        batch_size = 32
        for start in range(0, len(chunks), batch_size):
            end = start + batch_size
            self._collection.add(
                ids=ids[start:end],
                documents=texts[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )

        logger.info("Indexed %s chunk(s) into Chroma collection %s", len(chunks), self.collection_name)
        return len(chunks)

    def similarity_search(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict]:
        if self.count() == 0:
            return []

        k = top_k or self.settings.rag_top_k
        query_embedding = self.embedding_provider.embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, self.count()),
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]

        hits: list[dict] = []
        for index, document in enumerate(documents):
            distance = float(distances[index]) if index < len(distances) else 1.0
            # Cosine distance → similarity score in [0, 1]
            score = max(0.0, 1.0 - distance)
            hits.append(
                {
                    "id": ids[index] if index < len(ids) else f"hit_{index}",
                    "content": document or "",
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "score": score,
                    "distance": distance,
                }
            )
        return hits

    def reset(self) -> None:
        """Delete and recreate the collection."""
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            logger.debug("Collection delete skipped/failed for %s", self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )


def wipe_vector_db(persist_dir: Path | None = None) -> None:
    """Remove the persisted Chroma directory from disk."""
    global _store
    target = Path(persist_dir or VECTOR_DB_DIR)
    with _store_lock:
        _store = None
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            logger.info("Removed vector database directory: %s", target)
        target.mkdir(parents=True, exist_ok=True)


def get_vector_store(settings: Optional[Settings] = None) -> ChromaVectorStore:
    """Return process-wide Chroma vector store singleton."""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ChromaVectorStore(settings=settings or get_settings())
        return _store
