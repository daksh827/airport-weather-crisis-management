"""AOCC Knowledge RAG service — indexing, retrieval, and Gemini generation."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from backend.config import KNOWLEDGE_BASE_DIR, VECTOR_DB_DIR, Settings, get_settings
from backend.rag.loader import iter_knowledge_files, load_knowledge_documents
from backend.rag.retriever import KnowledgeRetriever, get_retriever
from backend.rag.splitter import split_documents
from backend.rag.vectorstore import ChromaVectorStore, get_vector_store

logger = logging.getLogger(__name__)

NO_MATCH_REPLY = (
    "I could not find relevant information inside the Airport Weather Crisis "
    "Management Manual."
)

_service_lock = threading.Lock()
_service: Optional["KnowledgeRAGService"] = None


class KnowledgeRAGService:
    """Indexes the AOCC knowledge base and answers with Gemini + retrieved context."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        vector_store: Optional[ChromaVectorStore] = None,
        retriever: Optional[KnowledgeRetriever] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.knowledge_dir = KNOWLEDGE_BASE_DIR
        self.vector_db_dir = VECTOR_DB_DIR
        self.vector_store = vector_store or get_vector_store(self.settings)
        self.retriever = retriever or KnowledgeRetriever(
            vector_store=self.vector_store,
            settings=self.settings,
        )
        self._gemini_model = None

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def ensure_indexed(self) -> dict:
        """Index knowledge base once when the vector store is empty."""
        if self.vector_store.is_indexed():
            status = self.get_status()
            logger.info(
                "Vector DB already indexed (%s chunks); skipping rebuild",
                status.get("chunks"),
            )
            return status
        return self.build_index(force=False)

    def build_index(self, *, force: bool = False) -> dict:
        """Load → split → embed → store knowledge documents."""
        with _service_lock:
            if force:
                self.vector_store.reset()
            elif self.vector_store.is_indexed():
                return self.get_status()

            documents = load_knowledge_documents(self.knowledge_dir)
            if not documents:
                logger.warning("No knowledge documents found in %s", self.knowledge_dir)
                return self.get_status()

            chunks = split_documents(
                documents,
                chunk_size=self.settings.rag_chunk_size,
                chunk_overlap=self.settings.rag_chunk_overlap,
            )
            self.vector_store.add_documents(chunks)
            status = self.get_status()
            logger.info(
                "Knowledge indexing complete: documents=%s chunks=%s model=%s",
                status.get("documents"),
                status.get("chunks"),
                status.get("embedding_model"),
            )
            return status

    def reindex(self) -> dict:
        """Clear the Chroma collection and rebuild from knowledge_base."""
        return self.build_index(force=True)

    def get_status(self) -> dict:
        document_count = len(list(iter_knowledge_files(self.knowledge_dir)))
        chunk_count = self.vector_store.count()
        return {
            "documents": document_count,
            "chunks": chunk_count,
            "embedding_model": self.vector_store.embedding_model,
            "vector_database": "ChromaDB",
            "indexed": chunk_count > 0,
            "knowledge_base": str(self.knowledge_dir),
            "vector_db_path": str(self.vector_db_dir),
            "collection": self.settings.rag_collection_name,
            "top_k": self.settings.rag_top_k,
        }

    # ------------------------------------------------------------------
    # Retrieval + generation
    # ------------------------------------------------------------------

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        return self.retriever.retrieve(question, top_k=top_k)

    def answer(
        self,
        question: str,
        *,
        live_context: str | None = None,
        top_k: int | None = None,
    ) -> dict:
        """Retrieve relevant chunks and generate a grounded Gemini answer."""
        hits = self.retrieve(question, top_k=top_k)
        if not hits:
            return {
                "reply": NO_MATCH_REPLY,
                "provider": "aocc-rag",
                "context_used": False,
                "sources": [],
                "retrieved_chunks": 0,
            }

        context_blocks = []
        sources: list[str] = []
        for index, hit in enumerate(hits, start=1):
            source = (hit.get("metadata") or {}).get("source", "manual")
            sources.append(str(source))
            context_blocks.append(
                f"[Excerpt {index} | source={source} | score={hit.get('score', 0):.2f}]\n"
                f"{hit.get('content', '').strip()}"
            )
        manual_context = "\n\n".join(context_blocks)

        try:
            reply = self._generate_with_gemini(
                question=question,
                manual_context=manual_context,
                live_context=live_context,
            )
            provider = "aocc-rag-gemini"
        except Exception as exc:
            logger.warning("Gemini generation failed (%s); using extractive fallback", exc)
            reply = self._extractive_fallback(question, hits, live_context=live_context)
            provider = "aocc-rag-extractive"

        return {
            "reply": reply,
            "provider": provider,
            "context_used": True,
            "sources": sorted(set(sources)),
            "retrieved_chunks": len(hits),
        }

    def _get_gemini_model(self):
        if self._gemini_model is not None:
            return self._gemini_model

        api_key = (self.settings.gemini_api_key or "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._gemini_model = genai.GenerativeModel(self.settings.gemini_model)
        return self._gemini_model

    def _generate_with_gemini(
        self,
        *,
        question: str,
        manual_context: str,
        live_context: str | None,
    ) -> str:
        import time

        model = self._get_gemini_model()
        live_block = live_context.strip() if live_context else "Not provided for this question."
        prompt = f"""You are the AOCC AI Assistant for Airport Operations Control Center staff.
Answer professionally and concisely using ONLY the supplied Airport Weather Crisis Management Manual excerpts and optional live operational context.

Rules:
- Prefer concrete operational guidance from the manual excerpts.
- If live operational context is provided, reconcile it with the manual.
- Do not invent procedures that are not supported by the excerpts.
- If the excerpts are insufficient, say you could not find relevant information in the Airport Weather Crisis Management Manual.
- Do not mention being an AI model.

Live operational context:
{live_block}

Manual excerpts:
{manual_context}

Operator question:
{question}

AOCC answer:"""

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = model.generate_content(prompt)
                text = (getattr(response, "text", None) or "").strip()
                if not text:
                    raise RuntimeError("Gemini returned an empty response")
                return text
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if attempt < 3 and ("429" in message or "quota" in message or "rate" in message):
                    delay = 2 ** attempt
                    logger.warning(
                        "Gemini rate-limited (attempt %s/4); retrying in %ss",
                        attempt + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise
        raise RuntimeError(f"Gemini generation failed: {last_error}")

    @staticmethod
    def _extractive_fallback(
        question: str,
        hits: list[dict],
        *,
        live_context: str | None,
    ) -> str:
        lines = [
            "Based on the Airport Weather Crisis Management Manual:",
            "",
        ]
        if live_context:
            lines.extend(["Live operational context:", live_context.strip(), ""])
        for hit in hits[:3]:
            source = (hit.get("metadata") or {}).get("source", "manual")
            excerpt = " ".join((hit.get("content") or "").split())
            if len(excerpt) > 420:
                excerpt = excerpt[:417] + "..."
            lines.append(f"• ({source}) {excerpt}")
        lines.extend(["", f"Question referenced: {question}"])
        return "\n".join(lines)


def get_knowledge_rag_service(settings: Optional[Settings] = None) -> KnowledgeRAGService:
    """Process-wide singleton so Chroma + embeddings load once."""
    global _service
    if _service is not None:
        return _service
    with _service_lock:
        if _service is None:
            _service = KnowledgeRAGService(settings=settings or get_settings())
        return _service
