# JobLens — Résumé-to-Roles Matching Platform

> Upload a résumé and JobLens surfaces the roles that actually fit — ranked by a
> two-pass engine combining **pgvector semantic similarity** with skill overlap,
> across multiple live career portals.

**Live demo:** _add your Vercel URL here after deploy_ · **API docs:** `/<api-url>/api/docs`

`FastAPI` · `SQLAlchemy 2.0` · `PostgreSQL + pgvector` · `Celery` · `Next.js 16` · `Tailwind v4` · `TypeScript` · `framer-motion`

---

## What it does

- **Résumé upload → structured parse → embedding.** A PDF is parsed (experience,
  skills, title) and embedded into a 384-dim vector.
- **Two-pass matching.** Pass 1 hard-filters by experience; Pass 2 scores
  `0.6 × semantic (pgvector cosine) + 0.4 × skill overlap` and ranks the results.
- **Multi-portal ingestion.** Live job data from Greenhouse/Lever/Amazon public
  APIs + an Adzuna aggregator, normalised behind one schema; every posting keeps
  a real apply URL.
- **Browse + filter.** Faceted search with animated dropdowns, multi-select
  location (incl. whole-country) and company filters, quick experience presets,
  flip pagination, and a job-detail drawer.
- **Continuous alerts.** Subscribe a résumé and a scheduled worker pushes only
  the *new* matches over time.

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
- **Applied ML/IR:** vector embeddings + approximate-nearest-neighbour search
  with a transparent, weighted scoring function.
- **Production thinking:** Alembic-owned schema, env-driven config with a
  production-secret guard, CORS, bearer-token auth scoping résumé PII, and a
  memory-aware deploy (torch-free embedding provider for free-tier hosting).
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
