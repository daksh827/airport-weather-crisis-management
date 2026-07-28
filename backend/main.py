"""FastAPI application entry point.

Serve both AOCC APIs and the dashboard frontend:

    python -m uvicorn backend.main:app --reload

Then open http://localhost:8000
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import (
    DOCUMENTS_DIR,
    KNOWLEDGE_BASE_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
    UPLOADS_DIR,
    VECTOR_DB_DIR,
    VECTORSTORE_DIR,
    Settings,
    get_settings,
)
from backend.routes import api_router
from backend.schemas import success_response

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for the application."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
        root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


logger = logging.getLogger("aocc")


def _ensure_runtime_directories() -> None:
    for path in (
        DOCUMENTS_DIR,
        UPLOADS_DIR,
        VECTORSTORE_DIR,
        VECTOR_DB_DIR,
        KNOWLEDGE_BASE_DIR,
        STATIC_DIR / "images",
    ):
        path.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown hooks."""
    settings = get_settings()
    configure_logging(settings.log_level)
    _ensure_runtime_directories()
    logger.info(
        "Starting %s v%s (weather=%s, chat=%s)",
        settings.app_name,
        settings.app_version,
        settings.weather_provider,
        settings.chat_provider,
    )

    # Phase 7B — ensure Chroma knowledge index exists (build only if missing)
    try:
        from backend.rag.rag_service import get_knowledge_rag_service

        status = get_knowledge_rag_service(settings).ensure_indexed()
        logger.info(
            "RAG ready indexed=%s documents=%s chunks=%s model=%s",
            status.get("indexed"),
            status.get("documents"),
            status.get("chunks"),
            status.get("embedding_model"),
        )
    except Exception:
        logger.exception("RAG startup indexing failed; assistant will degrade gracefully")

    yield
    logger.info("Shutting down AOCC application")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory with middleware, routers, and exception handlers."""
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_name,
        description=(
            "Airport Operations Control Center (AOCC) dashboard and APIs for "
            "weather monitoring, operational severity classification, and "
            "AI-assisted recommendations. Phase 1 uses mock weather and mock chat; "
            "architecture supports Tomorrow.io and Gemini later."
        ),
        version=cfg.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        debug=cfg.debug,
    )

    # CORS
    origins = (
        ["*"]
        if cfg.cors_origins.strip() == "*"
        else [o.strip() for o in cfg.cors_origins.split(",") if o.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static assets & templates
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if not TEMPLATES_DIR.exists():
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # API routers
    app.include_router(api_router)

    # ------------------------------------------------------------------
    # Exception handlers — always return the standard envelope
    # ------------------------------------------------------------------


    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning("HTTP %s on %s: %s", exc.status_code, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": str(exc.detail),
                "data": {},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Request validation failed",
                "data": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error",
                "data": {"detail": str(exc)} if cfg.debug else {},
            },
        )

    # ------------------------------------------------------------------
    # Core pages / health
    # ------------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    async def index(request: Request, settings: Settings = Depends(get_settings)):
        """Serve the AOCC dashboard."""
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "airport_icao": settings.airport_icao,
                "airport_name": settings.airport_name,
                "airport_location": settings.airport_location,
            },
        )

    @app.get("/health", tags=["System"])
    async def health(settings: Settings = Depends(get_settings)):
        """Health check endpoint."""
        return success_response(
            {
                "status": "healthy",
                "app_name": settings.app_name,
                "version": settings.app_version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "weather_provider": settings.weather_provider,
                "chat_provider": settings.chat_provider,
            },
            message="Service is healthy",
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
