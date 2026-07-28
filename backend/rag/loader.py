"""Knowledge-base document loading for AOCC RAG (Phase 7B)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from backend.config import KNOWLEDGE_BASE_DIR

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}


class DocumentChunkSource:
    """Simple document container compatible with LangChain-style usage."""

    def __init__(self, page_content: str, metadata: dict | None = None) -> None:
        self.page_content = page_content
        self.metadata = metadata or {}


def _load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_docx(path: Path) -> str:
    try:
        import docx2txt

        text = docx2txt.process(str(path)) or ""
        if text.strip():
            return text
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning("docx2txt failed for %s: %s", path.name, exc)

    try:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
    except Exception as exc:
        raise RuntimeError(f"Unable to load DOCX: {path.name}") from exc


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required to load PDF knowledge documents") from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page_index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
            logger.debug("Loaded PDF page %s from %s", page_index + 1, path.name)
    return "\n\n".join(parts)


def load_file(path: Path) -> DocumentChunkSource:
    """Load a single supported knowledge document."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        content = _load_txt(path)
    elif suffix == ".docx":
        content = _load_docx(path)
    elif suffix == ".pdf":
        content = _load_pdf(path)
    else:
        raise ValueError(f"Unsupported document type: {path.suffix}")

    content = (content or "").strip()
    if not content:
        raise ValueError(f"Document is empty after extraction: {path.name}")

    return DocumentChunkSource(
        page_content=content,
        metadata={
            "source": path.name,
            "path": str(path),
            "extension": suffix,
        },
    )


def iter_knowledge_files(knowledge_dir: Path | None = None) -> Iterable[Path]:
    root = knowledge_dir or KNOWLEDGE_BASE_DIR
    if not root.exists():
        logger.warning("Knowledge base directory missing: %s", root)
        return []
    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    return files


def load_knowledge_documents(knowledge_dir: Path | None = None) -> list[DocumentChunkSource]:
    """Load all supported documents from the AOCC knowledge base."""
    documents: list[DocumentChunkSource] = []
    for path in iter_knowledge_files(knowledge_dir):
        try:
            documents.append(load_file(path))
            logger.info("Loaded knowledge document: %s", path.name)
        except Exception:
            logger.exception("Failed to load knowledge document: %s", path)
    return documents
