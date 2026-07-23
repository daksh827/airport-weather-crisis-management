"""RAG and chatbot services — mock chat now; RAG placeholders for future."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from backend.config import UPLOADS_DIR, Settings, get_settings
from backend.models import ChatResponse
from backend.rag import RAGProvider, get_rag_provider
from backend.services.severity_service import SeverityService, get_severity_service
from backend.services.weather_service import WeatherService, get_weather_service

logger = logging.getLogger(__name__)


class MockChatProvider:
    """Rule-based AOCC assistant used until Gemini + LangChain are wired."""

    def __init__(
        self,
        weather_service: WeatherService,
        severity_service: SeverityService,
    ) -> None:
        self.weather_service = weather_service
        self.severity_service = severity_service

    def reply(self, message: str) -> ChatResponse:
        text = message.strip().lower()
        now = datetime.now(timezone.utc)
        weather = self.weather_service.get_current_weather()
        severity = self.severity_service.assess_from_weather(weather)

        if any(token in text for token in ("hello", "hi", "hey", "good morning", "good evening")):
            content = (
                f"AOCC AI Assistant online for {weather.icao_code} "
                f"({weather.airport_name}). Current alert is "
                f"{severity.title}. How can I support operations?"
            )
        elif any(token in text for token in ("weather", "metar", "observation", "conditions")):
            content = (
                f"Current weather at {weather.icao_code}: "
                f"{weather.weather_description}. "
                f"Temp {weather.temperature}°C, visibility {weather.visibility:.0f} m, "
                f"wind {weather.wind_speed} kt from {weather.wind_direction}, "
                f"rainfall {weather.rainfall} mm, pressure {weather.pressure} hPa, "
                f"humidity {weather.humidity}%."
            )
        elif any(token in text for token in ("severity", "level", "crisis", "alert", "status")):
            factors = "; ".join(severity.contributing_factors) or "None listed"
            content = (
                f"{severity.title}. {severity.description} "
                f"Contributing factors: {factors}. "
                f"Recommended action: {severity.recommended_action}"
            )
        elif any(token in text for token in ("action", "recommend", "guidance", "what should", "advise")):
            content = (
                f"Operational guidance (Level {severity.level.value}): "
                f"{severity.operational_guidance} "
                f"Immediate recommended action: {severity.recommended_action}"
            )
        elif any(token in text for token in ("visibility", "lvp", "fog")):
            content = (
                f"Visibility at {weather.icao_code} is {weather.visibility:.0f} m. "
                f"LVP considerations apply when visibility approaches Category I/II "
                f"minima. Current severity: {severity.title}."
            )
        elif any(token in text for token in ("wind", "gust", "crosswind")):
            content = (
                f"Wind is {weather.wind_speed} kt from {weather.wind_direction}. "
                f"Monitor runway crosswind components and coordinate with ATC if "
                f"gusts approach aircraft limits. Severity: {severity.title}."
            )
        elif any(token in text for token in ("rain", "precip", "storm", "thunder")):
            content = (
                f"Rainfall observation: {weather.rainfall} mm — "
                f"{weather.weather_description}. "
                f"Assess runway contamination and holding-point safety. "
                f"Severity: {severity.title}."
            )
        elif any(token in text for token in ("airport", "vidp", "delhi", "igi")):
            content = (
                f"{weather.airport_name} ({weather.icao_code}) — "
                f"{weather.location}. Monitoring weather-driven operational impact "
                f"for AOCC decision support."
            )
        elif any(token in text for token in ("rag", "document", "sop", "manual", "search")):
            content = (
                "Document search (RAG) is not active yet. Upload SOPs via the "
                "upload API; they will be stored for future FAISS + Gemini retrieval."
            )
        elif any(token in text for token in ("help", "commands", "what can")):
            content = (
                "I can summarize current weather, explain the alert level, and "
                "outline operational guidance. Ask about visibility, wind, rainfall, "
                "severity, or recommended actions."
            )
        else:
            content = (
                f"I registered your query. Based on live mock telemetry for "
                f"{weather.icao_code}, conditions are '{weather.weather_description}' "
                f"with alert {severity.title}. Ask about weather, severity, or "
                f"recommended actions for a focused brief."
            )

        return ChatResponse(
            reply=content,
            provider="mock",
            context_used=False,
            timestamp=now,
        )


class GeminiChatProvider:
    """Placeholder for future LangChain + Google Gemini integration."""

    def reply(self, message: str) -> ChatResponse:
        raise NotImplementedError(
            "Gemini chat provider is not implemented yet. "
            "Set CHAT_PROVIDER=mock or wire LangChain + Gemini."
        )


class RAGService:
    """Coordinates uploads, placeholder RAG, and chat responses."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        rag_provider: Optional[RAGProvider] = None,
        weather_service: Optional[WeatherService] = None,
        severity_service: Optional[SeverityService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.rag_provider = rag_provider or get_rag_provider(self.settings)
        self.weather_service = weather_service or get_weather_service()
        self.severity_service = severity_service or SeverityService(
            settings=self.settings,
            weather_service=self.weather_service,
        )
        self.uploads_dir = UPLOADS_DIR
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._chat = self._build_chat_provider()

    def _build_chat_provider(self):
        provider_name = (self.settings.chat_provider or "mock").strip().lower()
        if provider_name in {"gemini", "langchain", "google"}:
            logger.warning(
                "Gemini chat selected but not implemented; falling back to mock."
            )
        return MockChatProvider(self.weather_service, self.severity_service)

    def chat(self, message: str, session_id: Optional[str] = None) -> dict:
        """Generate an assistant reply (mock until Gemini is connected)."""
        # Future: retrieve RAG context via self.rag_provider.search(message)
        _ = self.rag_provider.search(message)
        response = self._chat.reply(message)
        return {
            "reply": response.reply,
            "provider": response.provider,
            "context_used": response.context_used,
            "timestamp": response.timestamp.isoformat(),
            "session_id": session_id or str(uuid.uuid4()),
        }

    async def save_upload(self, file: UploadFile) -> dict:
        """Persist an uploaded document for future RAG indexing."""
        original = file.filename or "unnamed.bin"
        safe_name = self._sanitize_filename(original)
        unique_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{safe_name}"
        destination = self.uploads_dir / unique_name

        content = await file.read()
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(
                f"File exceeds maximum upload size of {self.settings.max_upload_size_mb} MB"
            )

        destination.write_bytes(content)
        ingest_result = self.rag_provider.ingest_file(destination)
        logger.info("Upload stored at %s (rag_indexed=%s)", destination, False)

        return {
            "filename": original,
            "saved_as": unique_name,
            "size_bytes": len(content),
            "content_type": file.content_type,
            "status": "stored",
            "rag_indexed": False,
            "note": ingest_result.get(
                "message",
                "Stored for future RAG indexing. Embeddings are not generated yet.",
            ),
        }

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        cleaned = Path(name).name
        cleaned = re.sub(r"[^\w.\-]+", "_", cleaned)
        return cleaned[:180] or "upload.bin"


def get_rag_service() -> RAGService:
    """FastAPI dependency factory for RAGService."""
    return RAGService()
