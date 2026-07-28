"""Semantic text splitting for AOCC RAG chunks (Phase 7B)."""

from __future__ import annotations

import logging
from typing import Sequence

from backend.config import get_settings
from backend.rag.loader import DocumentChunkSource

logger = logging.getLogger(__name__)


def split_documents(
    documents: Sequence[DocumentChunkSource],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[DocumentChunkSource]:
    """Split documents into overlapping character chunks."""
    settings = get_settings()
    size = chunk_size or settings.rag_chunk_size
    overlap = chunk_overlap or settings.rag_chunk_overlap
    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        use_langchain = True
    except ImportError:
        logger.warning("langchain-text-splitters unavailable; using local splitter")
        use_langchain = False
        splitter = None

    chunks: list[DocumentChunkSource] = []
    for doc in documents:
        if use_langchain and splitter is not None:
            parts = splitter.split_text(doc.page_content)
        else:
            parts = _local_split(doc.page_content, size=size, overlap=overlap)

        for index, part in enumerate(parts):
            text = part.strip()
            if not text:
                continue
            metadata = dict(doc.metadata)
            metadata.update(
                {
                    "chunk_index": index,
                    "chunk_count": len(parts),
                }
            )
            chunks.append(DocumentChunkSource(page_content=text, metadata=metadata))

    logger.info(
        "Split %s document(s) into %s chunk(s) (size=%s overlap=%s)",
        len(documents),
        len(chunks),
        size,
        overlap,
    )
    return chunks


def _local_split(text: str, *, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return parts
