"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"
DOCUMENTS_DIR = BASE_DIR / "documents"
UPLOADS_DIR = BASE_DIR / "uploads"
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent / "knowledge_base"
VECTOR_DB_DIR = Path(__file__).resolve().parent / "vector_db"


class Settings(BaseSettings):
    """Runtime settings for the AOCC application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "AI-Powered Airport Weather Crisis Management System"
    app_version: str = "1.0.0"

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    weather_api_key: str = ""
    gemini_api_key: str = ""

    # Airport defaults - Delhi IGI (VIDP)
    airport_icao: str = "VIDP"
    airport_name: str = "Indira Gandhi International Airport"
    airport_location: str = "New Delhi, India"
    airport_iata: str = "DEL"

    # Weather provider switch: "mock" | "tomorrow_io" (future)
    weather_provider: str = "mock"

    # Chat provider switch: "mock" | "gemini" | "aocc" (live + RAG)
    chat_provider: str = "mock"

    # Phase 7B RAG
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5
    rag_collection_name: str = "aocc_knowledge_base"
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    rag_min_score: float = 0.15

    log_level: str = "INFO"
    cors_origins: str = "*"
    max_upload_size_mb: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (dependency-injection friendly)."""
    return Settings()
