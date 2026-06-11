"""
Application configuration (pydantic-settings).

Single committed stack: PostgreSQL + pgvector + Redis/Celery. There is no
SQLite / in-process fallback — local dev runs the same stack via docker-compose.
"""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "JobLens API"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── PostgreSQL ───────────────────────────────────────────────────────
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "job_matching_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # ── Database override (local dev) ────────────────────────────────────
    # If set (e.g. "sqlite:///./jobmatch_local.db"), this wins over the
    # Postgres parts above. Production leaves it empty and uses Postgres.
    DATABASE_URL: str | None = None

    # ── Redis / Celery ───────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    # Local dev: run tasks inline (no broker/worker needed).
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ── Embeddings ───────────────────────────────────────────────────────
    # "gemini" = real semantic vectors via the Gemini API (fits the free
    # hosting tier because inference is an HTTP call, not a local model).
    # Output is MRL-truncated to EMBEDDING_DIMENSION, so the pgvector column
    # and HNSW index stay at 384 — no schema migration when switching.
    EMBEDDING_PROVIDER: Literal["sentence-transformers", "deterministic", "gemini"] = (
        "sentence-transformers"
    )
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    GOOGLE_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # ── File storage ─────────────────────────────────────────────────────
    UPLOAD_DIR: str = "/data/uploads"
    MAX_FILE_SIZE_MB: int = 10

    # ── Matching weights ─────────────────────────────────────────────────
    SEMANTIC_WEIGHT: float = 0.6
    SKILL_WEIGHT: float = 0.4

    # ── Ingestion ────────────────────────────────────────────────────────
    # Live HEAD-check each job URL at ingestion and drop dead links.
    # Auto-skipped in local/deterministic dev (see scrapers.is_valid_job_url).
    VERIFY_JOB_URLS: bool = True

    # Adzuna job aggregator (free tier). When both are set, the "Adzuna"
    # aggregator portal fetches thousands of real, cross-company jobs.
    # Get keys at https://developer.adzuna.com/ ; leave blank to disable.
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_COUNTRY: str = "in"  # ISO country for the Adzuna endpoint

    @property
    def adzuna_enabled(self) -> bool:
        return bool(self.ADZUNA_APP_ID and self.ADZUNA_APP_KEY)

    # ── Security ─────────────────────────────────────────────────────────
    SCRAPER_API_KEY: str = "change-me-in-production"

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Managed Postgres providers (Neon, Render, Heroku) hand out
            # "postgres://" or "postgresql://" URLs; SQLAlchemy needs the
            # psycopg2 driver spelled out. Normalise so a pasted URL just works.
            if url.startswith("postgres://"):
                url = "postgresql+psycopg2://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+psycopg2://" + url[len("postgresql://"):]
            return url
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_file_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.SCRAPER_API_KEY == "change-me-in-production":
                raise ValueError(
                    "SCRAPER_API_KEY must be set to a non-default value in production"
                )
            # Only enforce DB_PASSWORD when the discrete DB_* vars are actually
            # in use; a managed DATABASE_URL (Neon/Render) carries its own creds.
            if not self.DATABASE_URL and self.DB_PASSWORD == "postgres":
                raise ValueError("DB_PASSWORD must be changed in production")
        if abs((self.SEMANTIC_WEIGHT + self.SKILL_WEIGHT) - 1.0) > 1e-6:
            raise ValueError("SEMANTIC_WEIGHT + SKILL_WEIGHT must sum to 1.0")
        if self.EMBEDDING_PROVIDER == "gemini" and not self.GOOGLE_API_KEY:
            raise ValueError(
                "EMBEDDING_PROVIDER=gemini requires GOOGLE_API_KEY to be set"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
