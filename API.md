# API Reference

Base URL (production): `https://joblens-api-xi3l.onrender.com`
Interactive Swagger UI: [`/api/docs`](https://joblens-api-xi3l.onrender.com/api/docs) ·
ReDoc: `/api/redoc`

## Authentication

Résumé, matching, and subscription endpoints are **owner-scoped**. Register a
candidate to receive a one-time bearer token, then send it as:

```
Authorization: Bearer <access_token>
```

Re-registering the same email **rotates** the token (latest caller owns the
candidate's résumés). Ingestion uses a separate `X-API-Key` header.

---

## Auth (accounts)

Password-backed accounts. Passwords are hashed with **scrypt** (stdlib,
memory-hard, per-user random salt). Both endpoints return a session bearer token.

### `POST /api/auth/signup`
```jsonc
// request
{ "email": "you@example.com", "full_name": "Your Name", "password": "min-8-chars" }
// 201 — { id, email, full_name, created_at, access_token }
```
`409` if an account with that email already exists; an existing **guest**
record (no password) is upgraded in place.

### `POST /api/auth/login`
```jsonc
{ "email": "you@example.com", "password": "•••" }   // 200 → { …, access_token }
```
`401` on bad email/password (constant-time, doesn't reveal which). Login
**rotates** the token, invalidating prior sessions.

---

## Candidates

### `POST /api/candidates`  (guest)
Lightweight register-or-rotate by email, no password. Returns the bearer token
**once**. Kept for backward compatibility / quick guest use.

```jsonc
{ "email": "you@example.com", "full_name": "Your Name" }
// 201 — { id, email, full_name, created_at, access_token }
```

### `GET /api/candidates/me`  🔒
Returns the authenticated candidate. `401` without a valid token.

---

## Résumés

### `POST /api/resumes/upload`  🔒
`multipart/form-data` with a `file` field (PDF, size-capped). Returns `202`
immediately; parsing + embedding happen asynchronously.

```jsonc
{ "id": "uuid", "candidate_id": "uuid", "file_name": "resume.pdf", "status": "pending" }
```

### `GET /api/resumes/{id}`  🔒
Poll for status: `pending → processing → embedding → ready` (or `failed`).
When `ready`, includes `parsed_data` (experience, skills, title).

---

## Jobs & search (public)

### `GET /api/jobs/search`
Faceted search. Query params (all optional):

| param | type | notes |
|-------|------|-------|
| `q` | string | free-text over title + description |
| `location` | csv | multi-location OR; a **country** name expands to all its cities |
| `work_model` | enum | `remote` · `hybrid` · `on-site` |
| `job_type` | enum | `full-time` · `contract` · `internship` |
| `industry` | string | |
| `experience_min` / `experience_max` | int | |
| `salary_min` / `salary_max` | int | |
| `posted_within_days` | int | 1–365 |
| `companies` | csv | filter to specific companies |
| `sources` | csv | filter to specific portals |
| `sort_by` | enum | `date` · `relevance` · `salary` |
| `include_facets` | bool | aggregated counts per filter dimension |
| `limit` / `offset` | int | pagination (limit ≤ 300) |

Returns `{ total, jobs[], facets }`.

### `GET /api/jobs/recent`
Recent active jobs (`days`, `source`, `location`, `limit`).

### `GET /api/jobs/options`
Distinct filter values from live data: `locations`, `countries`, `industries`,
`titles`, `companies`, `sources`, `work_models`, `job_types`. Powers the UI
dropdowns so users only pick values that return results.

### `GET /api/portals`
Configured career portals with `{ company, careers_url, live, ats }`.

### `GET /api/boards`
Integrated job-board directory.

---

## Matching  🔒

### `GET /api/jobs/eligible`
Jobs the candidate qualifies for (experience hard-filter), scored + ranked.

| param | notes |
|-------|-------|
| `resume_id` | required |
| `location`, `title_keyword`, `experience_min`, `max_experience`, `work_model`, `job_type`, `posted_within_days`, `sources` | filters |
| `match_mode` | `semantic` (default) or `direct` |
| `limit` | ≤ 200 |

`semantic` → `0.6×semantic + 0.4×skills`; `direct` → skill overlap only.
Each result carries `match_score`, `semantic_similarity`,
`skill_match_percentage`, `matched_skills[]` (with `found_in_resume`), and a
human-readable `reasoning`.

### `GET /api/jobs/matches`
Vector ANN + scalar filters, grouped by company; persists results to
`job_matches`.

---

## Subscriptions (continuous alerts)  🔒

| method | path | purpose |
|--------|------|---------|
| `POST` | `/api/subscriptions` | subscribe a résumé to ongoing alerts (filters, frequency, channel) |
| `GET` | `/api/subscriptions` | list the candidate's subscriptions |
| `DELETE` | `/api/subscriptions/{id}` | deactivate |

A scheduled worker scores each subscription against current jobs, dedupes
against past deliveries, and pushes only the **new** matches.

---

## Ingestion

### `POST /api/scraper-webhook`  (`X-API-Key`)
Bulk upsert jobs `{ source, jobs[] }` — race-safe on `(source, source_id)`.

### `POST /api/ingest`  (`X-API-Key`)
Trigger fetch + upsert for selected (or all) configured companies.

---

## Health

### `GET /api/health`
`{ status, service, version, database, active_jobs, candidates, ready_resumes }`.
