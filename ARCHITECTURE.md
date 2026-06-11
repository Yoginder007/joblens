# Architecture

This document explains how JobLens is structured and *why* — the design
decisions, trade-offs, and the data flow end to end.

## 1. System overview

```
┌────────────────────┐      HTTPS / JSON       ┌─────────────────────────┐
│  Next.js 16 (Vercel)│ ───────────────────────▶│   FastAPI  (Render)      │
│  App Router · TSX   │ ◀───────────────────────│   domain-driven services │
│  Tailwind v4        │   Bearer-token auth      │   + Celery workers       │
└────────────────────┘                          └───────────┬─────────────┘
                                                             │ SQLAlchemy 2.0
                                                             ▼
                                              ┌─────────────────────────────┐
                                              │ PostgreSQL + pgvector (Neon) │
                                              │ HNSW index for ANN search    │
                                              └─────────────────────────────┘
        External job sources ───▶ ingestion ───▶ jobs table (+ embeddings)
        (Greenhouse · Lever · Amazon · Adzuna)
```

Three independently deployable tiers, connected only by HTTP and a database URL.
Each can be scaled, redeployed, or swapped without touching the others.

## 2. Backend: domain-driven design

The backend is organised by **business domain**, not by technical layer. Each
domain is a self-contained vertical slice:

```
backend/app/domains/<domain>/
  models.py       SQLAlchemy ORM (tables)
  schemas.py      Pydantic request/response contracts
  repository.py   all data-access / query logic (the only place that touches the DB session for reads/writes)
  service.py      business logic, transaction boundaries (pure of HTTP concerns)
  router.py       FastAPI routes (HTTP in, schema out — thin)
```

Domains: `candidates`, `resumes`, `jobs`, `matching`, `subscriptions`,
`ingestion`, `health`.

**Why this layout.** A new engineer can open one folder and understand a whole
feature without spelunking across `models/`, `views/`, `serializers/` trees. It
also enforces dependency direction: `router → service → repository → model`.
Routers never write SQL; services never parse HTTP.

### Cross-cutting core (`app/core/`)
- **`config.py`** — `pydantic-settings`, env-driven, with a production-secret
  guard (`model_validator`) that refuses to boot with default secrets when
  `ENVIRONMENT=production`, and normalizes managed `postgres://` URLs to the
  psycopg2 driver.
- **`types.py`** — dialect-aware `GUID` / `JSONType` / `Vector` column types.
  This is the key abstraction that lets the **same ORM models** run on
  PostgreSQL (prod, native `uuid`/`jsonb`/`vector`) and SQLite (local dev,
  `char(36)`/`json`) with **no `if dialect == ...` branching in models**.
- **`security.py`** — bearer-token hashing/verification.
- **`exceptions.py`** — domain exceptions mapped to HTTP responses centrally.
- **`database.py`** — lazy engine + session factory.

## 3. The matching engine

`app/domains/matching/service.py::calculate_match` is a **pure function**
(no DB, no I/O) — trivially unit-testable.

```
Pass 1 — Hard filter:  candidate_years >= job.required_experience   (else rejected)
Pass 2 — Score:
   semantic      = cosine(resume_vec, job_vec) mapped to 0–100
   skill_overlap = |matched canonical skills| / |required canonical skills| × 100
   Smart Match   = 0.6 × semantic + 0.4 × skill_overlap
   Direct Filter = skill_overlap            (semantic dropped on purpose)
```

**Alias-aware skills** (`app/services/skills.py`): both résumé and job skills are
normalized to canonical tokens via a curated synonym map, so `JS`, `javascript`,
and `java script` collapse to one skill before overlap is computed. Results carry
canonical display names and a generated "why matched" explanation.

**Retrieval.** On Postgres, candidate jobs are fetched with a pgvector
`ORDER BY embedding <=> :resume_vec` (ANN via an **HNSW** index) so we score the
nearest N rather than the whole table. The cosine distance from retrieval is
reused in scoring instead of recomputed. On SQLite (dev) the same interface is
backed by a Python cosine fallback.

## 4. Data flow: résumé → matches

```
1. POST /api/candidates            → upsert by email, issue one-time bearer token
2. POST /api/resumes/upload        → stream PDF to disk (size-capped), row=pending
                                      → Celery task: parse (pdfplumber+regex) → embed → ready
3. GET  /api/resumes/{id}          → client polls until status=ready
4. GET  /api/jobs/eligible?...     → hard-filter + score + rank (Smart or Direct mode)
```

Heavy work (PDF parse, embedding) runs in a **Celery task** so the upload request
returns immediately (`202 Accepted`). In production on the free tier, Celery runs
in **eager mode** (in-process) to avoid needing a separate Redis broker; the same
code runs with a real Redis broker + worker via `docker-compose`.

## 5. Ingestion

`app/domains/ingestion/` fetches from multiple sources behind one normalized
schema. Providers: **Greenhouse** & **Lever** public board APIs, **Amazon**
search.json (queried per major city for coverage), and the **Adzuna** aggregator
(thousands of cross-company postings; falls back gracefully when keys are unset).
Companies without a public API are served from a small **curated** real-posting
set so the catalogue stays representative.

Upserts are **race-safe**: on Postgres, `INSERT … ON CONFLICT (source, source_id)
DO UPDATE` keeps the catalogue idempotent under concurrent ingestion; SQLite uses
a check-then-write equivalent.

## 6. Schema ownership & migrations

Alembic **owns** the Postgres schema (`backend/alembic/`). The first migration
also runs `CREATE EXTENSION IF NOT EXISTS vector` and builds the HNSW index.
Local SQLite dev bootstraps tables directly on startup — migrations are a
Postgres concern only.

## 7. Notable trade-offs

| Decision | Why | Trade-off |
|----------|-----|-----------|
| Gemini API embeddings in prod (`gemini-embedding-001`) | `sentence-transformers`+torch needs >512 MB; free tier has 512 MB — an HTTP call needs ~0 | Real semantic vectors with no local model: résumés embed as `RETRIEVAL_QUERY`, jobs as `RETRIEVAL_DOCUMENT`, MRL-truncated to 384 dims + re-normalised so the pgvector schema stays provider-agnostic. Provider switches re-vector everything via key-protected `POST /api/reembed` (batched, rate-limit-aware) |
| Eager Celery in prod | avoids a paid Redis instance | no distributed worker pool in the demo (fine at demo scale) |
| Dialect-aware types vs. two model sets | one source of truth for models | a thin custom `TypeDecorator` layer to maintain |
| Bearer token (hashed) auth | scopes résumé PII without a full auth stack | not full session/OAuth (a documented next step) |

## 8. Testing

- **Backend:** `pytest` over the pure matching engine, skill normalization,
  scrapers/URL parsing, auth, config, and the Gemini provider (HTTP mocked) —
  run with `EMBEDDING_PROVIDER=deterministic` so no network or model download
  is needed (75 tests).
- **Frontend:** `npm run lint` + `npm run build` (type-checks the whole tree).
- **CI:** GitHub Actions provisions a pgvector Postgres service and runs
  migrations + tests against the **real** database path.
