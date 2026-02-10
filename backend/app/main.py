"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.routes.approve import router as approve_router
from backend.app.api.routes.generate import router as generate_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.post_context import router as post_context_router
from backend.app.api.routes.presets import router as presets_router
from backend.app.api.routes.refine import router as refine_router
from backend.app.core.logging import setup_logging
from backend.app.core.settings import settings
from backend.app.db.engine import init_db
from backend.app.db.migrations import run_migrations
from backend.app.models.presets import validate_presets

setup_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("app_start")
    logger.info("config_loaded: %s", settings.safe_dump())
    init_db()
    run_migrations()
    validate_presets()
    if settings.score_recompute_enabled:
        from backend.app.core.scheduler import start_score_recomputation_scheduler

        start_score_recomputation_scheduler(settings.score_recompute_interval_seconds)
    logger.info("LI Reply Generator API ready")
    yield
    if settings.score_recompute_enabled:
        from backend.app.core.scheduler import stop_score_recomputation_scheduler

        stop_score_recomputation_scheduler()
    logger.info("LI Reply Generator API shutting down")


app = FastAPI(
    title="LI Reply Generator API",
    version="0.1.0",
    description="Backend API for the LinkedIn Reply Generator.",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler: log details, return safe generic message (AC4)."""
    from backend.app.core.errors import normalize_unknown_error

    error = normalize_unknown_error(exc, operation=f"{request.method} {request.url.path}")
    return JSONResponse(
        status_code=error.http_status,
        content={"detail": error.user_message},
    )


app.include_router(health_router, tags=["health"])
app.include_router(post_context_router, tags=["post-context"])
app.include_router(generate_router, tags=["generate"])
app.include_router(approve_router, tags=["approve"])
app.include_router(presets_router, tags=["presets"])
app.include_router(refine_router, tags=["refine"])
