# JobLens — Development & Improvement Playbook

> The standard operating procedure for **every** dev/improvement task on this repo.
> Follow it top-to-bottom. The goal is a tight, *self-verifying* loop so we stop
> guessing — especially on the frontend, where "did it actually look right?" has
> been the bottleneck.

---

## 0. Golden rules (read once, internalize)

1. **Never edit `.tsx`/`.ts` with PowerShell `Set-Content`/`Out-File`** — it mangles
   UTF-8 (`×`→`Ã—`, `é`→`Ã©`) and clips `??`→`?`. Use the editor/Write tools or a
   Python script writing `encoding="utf-8"`.
2. **Next.js here is non-standard.** Before writing Next-specific code, consult
   `frontend/node_modules/next/dist/docs/` (see `frontend/AGENTS.md`).
3. **One change → one verification.** Don't stack five edits then test. Small steps,
   verified, are faster than big steps debugged.
4. **A task is not "done" until it is *verified done*** — green tests for backend,
   a screenshot you actually looked at for frontend. "Should work" ≠ done.
5. **Embeddings must never mix providers.** Switching `EMBEDDING_PROVIDER` requires a
   full re-embed (`POST /api/reembed`). Parsing *may* fall back; embeddings may not.

---

## 1. Environment / one-time setup

```powershell
# Backend (this machine: SQLite, no Docker/Postgres/Redis)
cd backend
python ../scripts/seed_local.py        # seed real URL-bearing jobs into SQLite
./run_local.ps1                        # http://localhost:8000/api/docs

# Frontend
cd frontend
npm install
npm run dev                            # http://localhost:3000

# One-time: install the screenshot harness (see §4)
cd frontend
npm i -D playwright
npx playwright install chromium
```

`run_local.ps1` sets `DATABASE_URL=sqlite://…`, `EMBEDDING_PROVIDER=deterministic`,
`CELERY_TASK_ALWAYS_EAGER=true`.

---

## 2. The improvement loop (applies to ALL tasks)

```
┌─ 1. FRAME ─────────────────────────────────────────────────────────────┐
│  Write the target in one sentence + an explicit acceptance bar.         │
│  e.g. "Browse cards: tighten vertical rhythm + add company logos.       │
│        Done when: no layout shift on hover, logos load for ≥8 known     │
│        companies, light+dark both pass, lint+build clean."              │
├─ 2. BASELINE ──────────────────────────────────────────────────────────┤
│  Capture current state (tests output / screenshot) BEFORE changing.     │
│  You cannot tell if you improved something you never measured.          │
├─ 3. CHANGE ────────────────────────────────────────────────────────────┤
│  Smallest meaningful edit toward the target.                            │
├─ 4. VERIFY ────────────────────────────────────────────────────────────┤
│  Backend → §3.   Frontend → §4 (lint + build + SCREENSHOT you read).    │
├─ 5. CRITIQUE ──────────────────────────────────────────────────────────┤
│  Compare result against the acceptance bar from step 1. List what's     │
│  still off (spacing, contrast, jank, a failing assertion).              │
├─ 6. LOOP ──────────────────────────────────────────────────────────────┤
│  If the bar isn't met AND we haven't hit diminishing returns → go to 3. │
│  Stop when: bar met, OR 3 iterations with no material gain (then        │
│  report the remaining gap honestly instead of thrashing).               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Stop condition matters.** Cap at ~3 visual iterations per element unless the user
asks for more. Report the residual gap; don't loop forever chasing pixels.

---

## 3. Backend verification (run every time backend changes)

```powershell
cd backend
# 1. Syntax — fast, catches the dumb stuff first
python -m py_compile (Get-ChildItem -Recurse -Filter *.py app, tests | % FullName)

# 2. Tests — local profile (deterministic embeddings, no network)
$env:EMBEDDING_PROVIDER="deterministic"; $env:ENVIRONMENT="local"
python -m pytest -q

# 3. Targeted run while iterating on one area
python -m pytest backend/tests/test_matching.py -q
```

Acceptance bar (backend): **py_compile clean + all pytest green.** The real
Postgres/pgvector path runs only in CI (`.github/workflows/ci.yml`) — don't assume
a PG-only change is verified locally; call it out as CI-gated.

Touch-area test map:
| You changed…                         | Run at minimum                         |
|--------------------------------------|----------------------------------------|
| `domains/matching/`, `services/embedding.py` | `test_matching.py`, `test_embedding_gemini.py` |
| `domains/ingestion/scrapers.py`      | `test_scrapers.py`                     |
| `services/skills.py`                 | `test_skills.py`                       |
| `services/parsing.py`                | `test_parsing_llm.py`                  |
| auth / candidates                    | `test_auth.py`                         |
| maintenance endpoints / tasks        | `test_maintenance.py`                  |

---

## 4. Frontend verification — the VISUAL loop (the important part)

The reason frontend work has been painful: changes need to be *seen*. The fix is to
make the UI produce **PNG screenshots an agent can read**. Claude's Read tool renders
PNG/JPG, so a screenshot script closes the loop without a human in front of the screen.

### 4a. Static gates (always, fast)
```powershell
cd frontend
npm run lint
npm run build          # build also type-checks — a green build ⇒ types OK
```

### 4b. Screenshot harness (`frontend/scripts/shoot.mjs`)
A small Playwright script that boots nothing itself — it assumes `npm run dev` is
already running on :3000 — navigates to the routes/states we care about, and writes
PNGs to `frontend/.shots/`. Capture **both themes** and **3 viewports** (mobile 390,
tablet 834, desktop 1440) because this app is theme- and breakpoint-heavy.

States worth shooting (extend per task):
- `/` Browse tab — list + sticky detail pane (desktop) and card grid + drawer (mobile)
- `/` Match tab — configure (wizard), processing, results dashboard
- Open dropdowns / filter panel (they have their own readability rules)
- Auth modal open
- Empty state (no results) and error banner

Run + review:
```powershell
# terminal A: npm run dev   (must be up first)
cd frontend; node scripts/shoot.mjs        # writes .shots/browse-desktop-dark.png etc.
```
Then **open each PNG with the Read tool and actually inspect it** against the
acceptance bar: alignment, contrast (esp. light mode — aurora must not wash out text),
hover/active states, spacing rhythm, no clipped text, no layout shift.

> `.shots/` is throwaway — add it to `.gitignore`.

### 4c. Acceptance bar (frontend)
**lint clean + build clean + screenshots reviewed in BOTH themes at the relevant
breakpoints, matching the framed target, with no regression in the states you didn't
intend to touch.**

---

## 5. Quick reference — what lives where

- Architecture & conventions: `CLAUDE.md`
- Next.js caveats: `frontend/AGENTS.md` → `frontend/node_modules/next/dist/docs/`
- Theme tokens: `frontend/src/app/globals.css` (`--fg`/`--bg`, `.glass`, `.bg-accent`)
- Shared motion variants: `frontend/src/lib/motion.ts` (reuse these; don't re-roll easings)
- API client (single source of backend calls): `frontend/src/lib/api.ts`
- Matching engine (pure): `backend/app/domains/matching/service.py::calculate_match`
- Scrapers / ATS providers: `backend/app/domains/ingestion/scrapers.py`

---

## 6. Definition of Done (paste into the PR / final message)

- [ ] Framed target + acceptance bar stated
- [ ] Backend: `py_compile` clean, `pytest` green (note any CI-only PG paths)
- [ ] Frontend: `lint` + `build` clean
- [ ] Frontend: screenshots reviewed — light **and** dark, relevant breakpoints
- [ ] No unintended regression in adjacent states
- [ ] Honest note on anything still short of the bar
