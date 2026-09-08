"""
Fact Knowledge Layer — FastAPI Application
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.db.database import check_database_health, init_db


# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)

    # Initialize database (create tables, enable pgvector)
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        raise

    # Ensure upload directory exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down %s", settings.app_name)


# ── App ──────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Generic PDF → Fact Knowledge Layer pipeline",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── Import and register routers ────────────────────────
    from app.api.documents import router as doc_router
    from app.api.claims import router as claims_router
    from app.api.relations import router as relations_router

    app.include_router(doc_router)
    app.include_router(claims_router)
    app.include_router(relations_router)

    # ── Health Check ───────────────────────────────────────

    @app.get("/api/health")
    def health_check():
        """Database and service health check."""
        db_health = check_database_health()

        # Check Ollama connectivity
        ollama_status = "unknown"
        try:
            import httpx
            resp = httpx.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=5,
            )
            if resp.status_code == 200:
                ollama_status = "connected"
            else:
                ollama_status = f"error ({resp.status_code})"
        except Exception:
            ollama_status = "unavailable"

        return {
            "status": db_health.get("status", "unhealthy"),
            "app": settings.app_name,
            "environment": settings.app_env,
            "database": db_health.get("database", "unknown"),
            "pgvector": db_health.get("pgvector", "unknown"),
            "ollama": ollama_status,
            "llm_model": settings.ollama_model,
            "embedding_model": settings.embedding_model,
            "embedding_dimension": settings.embedding_dimension,
        }

    # ── Frontend ───────────────────────────────────────────

    frontend_dir = Path(__file__).parent.parent / "frontend"

    @app.get("/")
    def serve_frontend():
        """Serve the frontend HTML."""
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
        return JSONResponse(
            {"message": "Frontend not yet built. Use API endpoints at /docs"},
            status_code=200,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
