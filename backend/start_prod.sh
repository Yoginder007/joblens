#!/usr/bin/env bash
# Production entrypoint (Render). Applies migrations, optionally seeds jobs on
# first boot, then serves the API. Run from the backend/ directory.
set -e

echo "→ Applying database migrations…"
alembic upgrade head

# Seed real jobs once, only if the DB is empty (idempotent). Controlled by
# SEED_ON_START so you can disable it after the first deploy.
if [ "${SEED_ON_START:-true}" = "true" ]; then
  echo "→ Seeding jobs (skipped automatically if already populated)…"
  python -m app.scripts.seed_prod || echo "  (seed skipped/failed — continuing)"
fi

echo "→ Starting API on port ${PORT:-8000}…"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
