"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.routes.approve import router as approve_router
from backend.app.api.routes.generate import router as generate_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.post_context import router as post_context_router
from backend.app.core.logging import setup_logging
from backend.app.core.settings import settings
from backend.app.db.migrations import run_migrations
from backend.app.models.presets import validate_presets

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("app_start")
    logger.info(
        "config_loaded: db_path=%s debug=%s",
        settings.app_db_path,
        settings.debug,
    )
    run_migrations()
    validate_presets()
    logger.info("LI Reply Generator API ready")
    yield
    logger.info("LI Reply Generator API shutting down")


app = FastAPI(
    title="LI Reply Generator API",
    version="0.1.0",
    description="Backend API for the LinkedIn Reply Generator.",
    lifespan=lifespan,
)

app.include_router(health_router, tags=["health"])
app.include_router(post_context_router, tags=["post-context"])
app.include_router(generate_router, tags=["generate"])
app.include_router(approve_router, tags=["approve"])
