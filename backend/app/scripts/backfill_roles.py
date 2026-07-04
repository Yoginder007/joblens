"""
CLI wrapper for the role backfill (see ingestion/service.backfill_roles).

Local/CLI use:
    cd backend
    python -m app.scripts.backfill_roles

On the deployed free tier (no shell) use the endpoint instead:
    POST /api/maintenance/backfill-roles   (X-API-Key)
"""
import logging

import app.db.base  # noqa: F401  (registers all mappers for CLI usage)
from app.domains.ingestion.service import backfill_roles

logging.basicConfig(level=logging.INFO, format="%(message)s")


if __name__ == "__main__":
    print(backfill_roles())
