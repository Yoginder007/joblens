# =============================================================================
# Multi-stage Dockerfile for the Job Aggregator API
#
# Key design decisions:
#   1. The sentence-transformers model (all-MiniLM-L6-v2, ~90 MB) is
#      downloaded and cached DURING the build phase so that containers
#      start instantly with zero network latency.
#   2. Requirements are installed in a separate layer before copying
#      the application code, so code changes don't re-download deps.
#   3. The app runs as a non-root user for security.
#   4. A single image serves both the API (uvicorn) and the Celery
#      worker — the entrypoint command is overridden in docker-compose.
# =============================================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies for psycopg2 and general tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python dependencies (cached layer) ─────────────────────────────
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Pre-download the embedding model into the image ─────────────────────────
# This avoids a ~90 MB download on every container start.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# ── Copy application code ──────────────────────────────────────────────────
COPY backend/ .

# ── Create non-root user ───────────────────────────────────────────────────
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /data/uploads && \
    chown -R appuser:appgroup /data/uploads

USER appuser

# ── Default command: run the API server ─────────────────────────────────────
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
