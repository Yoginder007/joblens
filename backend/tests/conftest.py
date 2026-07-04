import os

# Pure-logic tests don't touch the DB or download a model.
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("ENVIRONMENT", "local")

# Hermetic tests: FORCE external/paid scraper providers off, even if a developer
# has real keys in backend/.env — a stray live Apify run would cost money.
os.environ["APIFY_TOKEN"] = ""
os.environ["ADZUNA_APP_ID"] = ""
os.environ["ADZUNA_APP_KEY"] = ""

# TestClient sends every request from one fake IP — per-IP limits would 429
# unrelated tests. The limiter itself is covered by targeted tests.
os.environ["RATE_LIMIT_ENABLED"] = "false"
