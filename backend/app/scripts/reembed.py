"""
Re-embed all active jobs + ready résumés with the current embedding provider.

Run after switching EMBEDDING_PROVIDER (e.g. deterministic → gemini): vectors
from different providers live in incompatible spaces and must be regenerated
together. Local usage:

    cd backend
    $env:EMBEDDING_PROVIDER="gemini"; $env:GOOGLE_API_KEY="..."  # PowerShell
    python -m app.scripts.reembed [--limit N]

In production (no shell on the free tier) use the API instead:
    POST /api/reembed  (X-API-Key)  →  GET /api/reembed/status
"""
import argparse
import logging

from app.domains.ingestion.service import reembed_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="re-embed at most N jobs and N resumes (smoke test)")
    parser.add_argument("--pause", type=float, default=15.0,
                        help="seconds between Gemini batches (rate-limit budget)")
    args = parser.parse_args()

    result = reembed_all(limit=args.limit, pause_s=args.pause)
    print(f"Re-embedded {result['jobs']} jobs and {result['resumes']} resumes "
          f"with provider={result['provider']}")


if __name__ == "__main__":
    main()
