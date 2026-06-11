# JobLens — Résumé-to-Roles Matching Platform

> Upload a résumé and JobLens surfaces the roles that actually fit — ranked by a
> two-pass engine combining **pgvector semantic similarity** with skill overlap,
> across multiple live career portals.

**🔗 Live demo:** [joblens-match.vercel.app](https://joblens-match.vercel.app) · **API + Swagger docs:** [joblens-api-xi3l.onrender.com/api/docs](https://joblens-api-xi3l.onrender.com/api/docs)

`FastAPI` · `SQLAlchemy 2.0` · `PostgreSQL + pgvector` · `Celery` · `Next.js 16` · `Tailwind v4` · `TypeScript` · `framer-motion`

> ℹ️ The backend runs on a free Render instance that sleeps after ~15 min idle, so
> the **first request may take ~30–50 s to wake** — subsequent calls are fast.

📚 **Docs:** [Architecture](ARCHITECTURE.md) · [API reference](API.md) · [Deployment guide](DEPLOY.md) · [Contributing](CONTRIBUTING.md)

---

## What it does

- **Résumé upload → structured parse → embedding.** A PDF is parsed into a
  structured profile by **Gemini Flash structured extraction** (JSON-schema
  output: title, years, categorised skills, domains, education) with a
  deterministic regex fallback so uploads never break on provider issues —
  then embedded into a 384-dim vector. Production embeddings come
  from **Gemini (`gemini-embedding-001`)** — résumés embed as retrieval
  *queries* and jobs as retrieval *documents*, MRL-truncated to 384 dims and
  re-normalised, so real semantic vectors fit the same pgvector schema (and the
  free hosting tier, since inference is an API call rather than a local model).
- **Two matching modes.**
  - **Smart Match** — `0.6 × semantic (pgvector cosine) + 0.4 × skill overlap`.
  - **Direct Filter** — skill-overlap only, driven by the user's hard filters
    (location/experience/etc.); avoids letting an approximate semantic signal
    depress scores when a job description omits explicit skills.
  Both apply an experience hard-filter first, then rank.
- **Alias-aware skills.** A canonical normalizer means `JS↔JavaScript`,
  `k8s↔Kubernetes`, `postgres↔PostgreSQL` all count as the same skill, with a
  plain-English "why this matched" explanation per result.
- **Multi-portal ingestion.** Live job data from Greenhouse/Lever/Amazon public
  APIs + an Adzuna aggregator, normalised behind one schema; every posting keeps
  a real apply URL.
- **Browse + filter.** Faceted search with animated dropdowns, multi-select
  location (incl. whole-country) and company filters, quick experience presets,
  flip pagination, and a job-detail drawer.
- **Continuous alerts.** Subscribe a résumé and a scheduled worker pushes only
  the *new* matches over time. In the free-tier deploy the schedule is driven
  by a GitHub Actions cron (nightly catalogue refresh + stale-job cleanup,
  daily/weekly alert runs) hitting key-protected maintenance endpoints.

## Architecture

```
Next.js 16 (Vercel)  ──HTTPS──▶  FastAPI (Render)  ──▶  PostgreSQL + pgvector (Neon)
  App Router, Tailwind v4,           domain-driven           HNSW vector index
  framer-motion, bearer-token        services + Celery        for ANN search
  session in localStorage            workers (alerts)
```

**Backend is domain-driven** — each domain (`candidates`, `resumes`, `jobs`,
`matching`, `subscriptions`, `ingestion`, `health`) is a self-contained
`models · schemas · repository · service · router` slice. A dialect-aware type
layer (`core/types.py`) lets the *same* models run on Postgres (prod) and SQLite
(local dev) with no `if`-branching.

```
backend/app/
  core/        config · database · types (GUID/JSONType/Vector) · security · exceptions
  domains/<x>/ models · schemas · repository · service · router
  services/    embedding (pluggable provider) · parsing  (pure, infra-free)
  workers/     celery app · tasks · beat schedules
  alembic/     migrations own the Postgres schema
frontend/src/
  app/         pages, theme, icon
  components/  dropdowns, job cards, filters, drawer, aurora background
  lib/         api client · session · motion variants
```

## What this project demonstrates

- **System design:** clean layering, a repository pattern, race-safe upserts
  (`INSERT … ON CONFLICT`), and a single schema that targets two databases.
- **Applied ML/IR:** real Gemini embeddings with asymmetric task types
  (query vs document), approximate-nearest-neighbour search over pgvector, and
  a transparent, weighted scoring function — behind a pluggable provider so
  tests/CI run fully offline on deterministic vectors.
- **Production thinking:** Alembic-owned schema, env-driven config with a
  production-secret guard, CORS, bearer-token auth scoping résumé PII, and a
  memory-aware deploy (API-based embeddings — no torch — for free-tier hosting,
  with batched, rate-limit-aware re-embedding via a key-protected endpoint).
- **Frontend craft:** a cohesive dark/light "aurora" design system on CSS
  variables, accessible custom comboboxes, and purposeful motion.

## Run locally (no Docker required)

```powershell
# Backend — SQLite + in-process tasks + deterministic embeddings
cd backend
pip install -r requirements-dev.txt
python ../scripts/seed_local.py     # seed real, URL-bearing jobs
./run_local.ps1                     # http://localhost:8000/api/docs

# Frontend
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

The committed production stack (Postgres + pgvector + Redis/Celery) also runs
end-to-end via `docker-compose up`.

## Tests

```bash
cd backend && EMBEDDING_PROVIDER=deterministic ENVIRONMENT=local pytest
cd frontend && npm run lint && npm run build
```

## Deployment (free tier)

Hosted across three free services — see [DEPLOY.md](DEPLOY.md) for the
step-by-step guide:

| Layer | Host | Notes |
|-------|------|-------|
| Database | **Neon** | free Postgres **with pgvector** |
| Backend | **Render** | free web service; `render.yaml` blueprint included |
| Frontend | **Vercel** | free Next.js hosting |

---

Built by [Yoginder](https://github.com/Yoginder007).
