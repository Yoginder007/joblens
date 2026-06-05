# Contributing & Development Guide

Conventions and local workflow for JobLens. Even as a solo project, it follows
team-grade practices so the codebase stays consistent and reviewable.

## Local setup

**Prerequisites:** Python 3.11+, Node 20+. No Docker required for dev.

```bash
# Backend — SQLite + in-process tasks + deterministic embeddings
cd backend
python -m venv .venv && . .venv/Scripts/activate   # (Windows) or source .venv/bin/activate
pip install -r requirements-dev.txt
python ../scripts/seed_local.py        # seed real, URL-bearing jobs
./run_local.ps1                        # → http://localhost:8000/api/docs

# Frontend
cd frontend
npm install
npm run dev                            # → http://localhost:3000
```

The full production stack (Postgres + pgvector + Redis/Celery) runs via
`docker-compose up`.

## Project layout

```
backend/app/
  core/        cross-cutting: config, db, types, security, exceptions
  domains/<x>/ vertical slices: models · schemas · repository · service · router
  services/    pure, infra-free logic (embedding, parsing, skills)
  workers/     Celery app · tasks · beat schedules
  alembic/     migrations (own the Postgres schema)
frontend/src/
  app/         App-Router pages, theme, icon
  components/  UI components
  lib/         api client · session · motion
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the *why*.

## Coding conventions

**Python**
- Keep routers thin: HTTP in → service → schema out. No SQL in routers.
- All DB access goes through a domain `repository`.
- Services raise domain exceptions (`app/core/exceptions.py`), never `HTTPException`.
- Pure logic (matching, skills, parsing) stays in `app/services/` — no DB/HTTP — so it's unit-testable.
- New schema changes = a new Alembic revision; never `create_all` on Postgres.
- Type hints everywhere; `pydantic` models at every API boundary.

**TypeScript / React**
- Components are typed; API calls go through `lib/api.ts` (single source for the contract).
- Theming uses CSS variables `--fg` / `--bg`; use `text-fg/xx`, `bg-fg/[x]`,
  `.glass`, `.bg-accent`. Text on a solid accent uses `on-accent`.
- Respect `prefers-reduced-motion` for animations.

## Testing & checks (run before every commit)

```bash
# Backend
cd backend
python -m py_compile $(git ls-files 'app/*.py' 'tests/*.py')
EMBEDDING_PROVIDER=deterministic ENVIRONMENT=local pytest

# Frontend
cd frontend
npm run lint
npm run build      # also type-checks
```

CI (GitHub Actions) runs the backend suite against a **real pgvector Postgres**
service plus the frontend lint/build on every push.

## Commit conventions

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     a user-facing feature
fix:      a bug fix
chore:    tooling / housekeeping
docs:     documentation only
refactor: no behaviour change
test:     tests only
```

Keep commits focused; describe the *why* in the body when non-obvious.

## Branching

`main` is always deployable (auto-deploys to Render + Vercel). Develop on
feature branches and open a PR into `main`.

## Environment variables

Never commit secrets. Copy the examples and fill locally:
- `backend/.env.example` → `backend/.env`
- `frontend/.env.example` → `frontend/.env.local`

Production values are set in the host dashboards (Render / Vercel), not in the repo.
