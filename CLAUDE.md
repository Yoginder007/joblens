# JobMatch AI — Project Guide

Full-stack job aggregator + résumé matcher. **Backend**: FastAPI + SQLAlchemy 2.0,
domain-driven. **Frontend**: Next.js 16 (App Router) + Tailwind v4 + framer-motion.

## Architecture (committed stack)
Production runs **PostgreSQL + pgvector + Redis/Celery** via `docker-compose`.
The same code runs locally on **SQLite + in-process Celery + deterministic
embeddings** — the two are bridged by dialect-aware column types, NOT by
scattered `if USE_SQLITE` branches.

- `backend/app/core/` — config, database (lazy engine), `types.py` (GUID/JSONType/Vector), security, exceptions, logging.
- `backend/app/domains/<x>/` — each domain = `models · schemas · repository · service · router`. Domains: candidates, resumes, jobs, matching, subscriptions, ingestion, health.
- `backend/app/services/` — pure, infra-free (embedding, parsing).
- `backend/app/workers/` — Celery app, tasks, beat schedules.
- `backend/alembic/` — migrations OWN the Postgres schema (never `create_all` on PG). SQLite dev auto-creates via `init_db()` on startup.
- `frontend/src/` — `app/` (pages), `components/`, `lib/` (api client, session, motion).

## Local dev (this machine: no Docker/Postgres/Redis; Python 3.14)
```powershell
cd backend
python ../scripts/seed_local.py   # seed real URL-bearing jobs into SQLite
./run_local.ps1                    # serves http://localhost:8000/api/docs
```
`run_local.ps1` sets `DATABASE_URL=sqlite://…`, `EMBEDDING_PROVIDER=deterministic`,
`CELERY_TASK_ALWAYS_EAGER=true`. Frontend: `cd frontend; npm run dev` → :3000.

## Verification (no live Postgres here)
- Backend: `python -m py_compile` over `app/ tests/`; `pytest` (set `EMBEDDING_PROVIDER=deterministic ENVIRONMENT=local`). Real PG path is exercised only in CI.
- Frontend: `npm run lint` then `npm run build` (build also type-checks).

## Conventions / gotchas
- **Auth**: `POST /api/candidates` returns a one-time bearer `access_token`; résumé/match/subscription endpoints require `Authorization: Bearer <token>`. Frontend persists it via `lib/session.ts` (localStorage).
- **Theme**: single source of truth is CSS vars `--fg` / `--bg` in `globals.css`; both themes share them. Use `text-fg/40`, `bg-fg/[0.04]`, `.glass`, `.bg-accent`. Text on a solid `bg-accent` uses `on-accent` (white in both themes); text on glass uses `text-fg`. Theme toggled via `ThemeToggle` + next-themes (class strategy).
- **Scrapers** (`domains/ingestion/scrapers.py`): each company is keyed by its **career-page URL**; `extract_board_token()` derives the ATS slug, the ATS API returns real per-posting IDs + URLs. `extract_job_id_from_url()` + `is_valid_job_url()` reject career-root pages (no posting id). Ingestion upsert refreshes `job_url` (see `_UPDATE_KEYS`).
- **NEVER** use PowerShell `Set-Content`/`Out-File` to rewrite `.tsx`/`.ts` in bulk — it mangles UTF-8 (× → Ã—, é → Ã©) and can clip `??`→`?`. Use the Edit/Write tools, or a Python script writing `encoding="utf-8"`.
- `frontend/AGENTS.md`: this Next.js version has breaking changes — consult `node_modules/next/dist/docs/` before writing Next-specific code.

## Status
Backend foundation + continuous-alerts pipeline complete and tested. Frontend
migrated to v2 API with dark/light aurora themes. Email alert delivery still
logs only (integration point in `subscriptions/service.py`); webhook channel works.
