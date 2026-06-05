"""
FastAPI application factory.

Schema is owned by Alembic (run ``alembic upgrade head`` before serving),
so startup does not create tables.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging()
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    if settings.is_sqlite:
        # Local dev: no Alembic — create the schema directly.
        from app.core.database import init_db

        init_db()
        logger.info("SQLite schema ensured (local dev)")
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    from app.domains.candidates.router import auth_router
    from app.domains.candidates.router import router as candidates_router
    from app.domains.health.router import router as health_router
    from app.domains.ingestion.router import router as ingestion_router
    from app.domains.jobs.router import boards_router
    from app.domains.jobs.router import router as jobs_router
    from app.domains.matching.router import router as matching_router
    from app.domains.resumes.router import router as resumes_router
    from app.domains.subscriptions.router import router as subscriptions_router

    for r in (
        health_router,
        auth_router,
        candidates_router,
        resumes_router,
        jobs_router,
        boards_router,
        matching_router,
        subscriptions_router,
        ingestion_router,
    ):
        app.include_router(r)

    return app


app = create_app()
