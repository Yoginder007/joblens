# JobLens — Résumé-to-Roles Matching Platform

A full-stack platform for aggregating job postings from multiple boards and matching candidates against them using vector embeddings and a two-pass scoring engine.

**Backend**: FastAPI + SQLAlchemy + pgvector · **Frontend**: Next.js + Tailwind CSS · **Processing**: Background workers (Celery or in-process threads)

---

## Architecture

```
┌───────────────────┐
│   Next.js Frontend │  (http://localhost:3000)
│   React + Tailwind │
└────────┬──────────┘
         │ HTTP / JSON
┌────────▼──────────┐      ┌──────────────────────┐
│   FastAPI Backend  │─────▶│  PostgreSQL + pgvector│
│   (uvicorn :8000)  │      │  or SQLite (local)    │
└────────┬──────────┘      └──────────────────────┘
         │ task dispatch
┌────────▼──────────┐      ┌──────────────────────┐
│   Celery Worker    │◀────▶│   Redis (broker)      │
│   (or in-process)  │      │   (local: threads)    │
└───────────────────┘      └──────────────────────┘
```

**Key Components:**
- **FastAPI** — Async HTTP API with Pydantic validation, OpenAPI docs
- **Next.js** — Modern React frontend with Tailwind CSS, dark theme
- **Celery + Redis** — Background workers for PDF parsing and embedding generation (production)
- **In-Process Threads** — Zero-dependency alternative for local development (no Redis needed)
- **PostgreSQL + pgvector** — Relational storage with 384-dim vector columns (production)
- **SQLite** — Zero-config database for local development
- **Sentence Transformers** — `all-MiniLM-L6-v2` model (or mock embeddings for dev)

---

## Complete Pipeline Flow

```
                            ┌──────────────────────────────────────────────────┐
                            │                  DATA INGESTION                  │
                            └──────────────────────────────────────────────────┘

External Scraper ──POST──▶ /api/scraper-webhook ──▶ Validate + Upsert Jobs
(or seed script)           (X-API-Key auth)          into DB (source, source_id)
                                                         │
                                                         ▼
                                                   Generate Job Embedding
                                                   (background worker)


                            ┌──────────────────────────────────────────────────┐
                            │                CANDIDATE FLOW                    │
                            └──────────────────────────────────────────────────┘

User ──▶ POST /api/candidates ──▶ Upsert Candidate (by email)
         │                            │
         ▼                            ▼
     POST /api/resumes/upload ──▶ Save PDF to disk
         │                            │
         │                     ┌──────▼──────────────────────────────┐
         │                     │      Background Worker Task         │
         │                     │                                     │
         │                     │  1. Extract text (pdfplumber)       │
         │                     │  2. Parse resume (regex / LLM)      │
         │                     │     → name, title, experience,      │
         │                     │       skills, education             │
         │                     │  3. Generate embedding              │
         │                     │     (SentenceTransformer / mock)     │
         │                     │  4. Update DB (status → ready)      │
         │                     └─────────────────────────────────────┘
         │
         ▼
     GET /api/resumes/{id} ──▶ Poll until status = "ready"


                            ┌──────────────────────────────────────────────────┐
                            │              JOB MATCHING ENGINE                 │
                            └──────────────────────────────────────────────────┘

     GET /api/jobs/eligible ──▶ Hard Filter: candidate_exp >= job_requirement
         │                          Optional: location, title, max_experience
         │                          Score each match → return ranked list
         │
         │   OR
         │
     GET /api/jobs/matches ──▶ Two-Pass Engine:
         │                         Pass 1: Hard filter (experience)
         │                         Pass 2: Score = 60% semantic + 40% skill overlap
         │                         Persist results to job_matches table
         │
         ▼
     GET /api/jobs/recent ──▶ Browse all jobs (no resume needed)
                                Filter by: days, source, location
```

---

## Quick Start (Local Development)

### Prerequisites
- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`

### 1. Backend Setup

```bash
# Clone & enter the project
cd api_project

# Install Python dependencies
pip install -r requirements-local.txt

# Configure environment (defaults work out of the box)
cp .env.example .env
# The .env already has USE_SQLITE=true and USE_MOCK_EMBEDDINGS=true

# Start the API server
python -m uvicorn app.main:app --port 8000

# Verify
curl http://localhost:8000/api/health
# Open http://localhost:8000/api/docs for interactive API docs
```

### 2. Seed Real Jobs

```bash
# Fetch live Amazon Bengaluru SDE jobs and seed into the database
python seed_real_jobs.py
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Open http://localhost:3000
```

### 4. Test the Full Flow

```bash
# Run the comprehensive test suite
python test_bugs.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check with DB stats (jobs, candidates, resumes) |
| `POST` | `/api/candidates` | Register/upsert a candidate (by email) |
| `POST` | `/api/resumes/upload` | Upload a PDF resume (async processing) |
| `GET` | `/api/resumes/{id}` | Get resume details + processing status |
| `GET` | `/api/tasks/{id}` | Check background task status |
| `GET` | `/api/jobs/search` | Search jobs by company/title/experience |
| `GET` | `/api/jobs/recent` | Browse all recent jobs (no resume needed) |
| `GET` | `/api/jobs/eligible` | Get eligible jobs for a resume (with filters) |
| `GET` | `/api/jobs/matches` | Run full two-pass matching engine |
| `POST` | `/api/scraper-webhook` | Ingest jobs from external scrapers |
| `GET` | `/api/boards` | List integrated job boards |

---

## Project Structure

```
api_project/
├── app/
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── config.py            # Pydantic settings (env-based)
│   ├── database.py          # Engine, session, pgvector init
│   ├── models.py            # SQLAlchemy ORM (Candidate, Resume, Job, JobMatch, JobBoard)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── dependencies.py      # Shared dependencies (API key auth)
│   ├── routes/
│   │   ├── health.py        # Health check with DB stats
│   │   ├── resumes.py       # Candidate registration + resume upload
│   │   ├── jobs.py          # Search, browse, eligible, matches
│   │   ├── boards.py        # Job board listing
│   │   └── webhooks.py      # Scraper webhook (bulk job ingest)
│   ├── services/
│   │   ├── embedding.py     # SentenceTransformer (lazy-loaded, thread-safe)
│   │   ├── parsing.py       # PDF extraction + regex-based resume parser
│   │   └── matching.py      # Two-pass matching engine with debug logging
│   └── worker/
│       ├── celery_app.py    # Celery configuration (production)
│       ├── local_runner.py  # In-process thread runner (local dev)
│       └── tasks.py         # Background tasks (process_resume, generate_job_embedding)
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx   # Root layout (fonts, metadata)
│   │   │   ├── page.tsx     # Main page (tab switcher: Browse / Match)
│   │   │   └── globals.css  # Global styles
│   │   ├── components/
│   │   │   ├── ResumeUploader.tsx   # Drag-and-drop PDF upload
│   │   │   ├── FilterPanel.tsx      # Experience, location, tech, board filters
│   │   │   ├── ProcessingState.tsx  # Resume processing progress stepper
│   │   │   ├── ResultsDashboard.tsx # Match results with stats + source tabs
│   │   │   ├── RecentJobsPanel.tsx  # Browse all jobs (grouped by source)
│   │   │   └── JobCard.tsx          # Individual job card with score badge
│   │   └── lib/
│   │       └── api.ts       # API client (all backend communication)
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.ts
│
├── seed_real_jobs.py        # Fetch + seed real Amazon jobs
├── test_bugs.py             # Comprehensive test suite
├── demo_e2e.py              # End-to-end demo script
├── requirements.txt         # Production dependencies
├── requirements-local.txt   # Local dev dependencies (lighter)
├── .env                     # Environment config
├── .env.example             # Template
├── Dockerfile               # Production container
├── docker-compose.yml       # Full stack (API + Worker + Postgres + Redis)
└── README.md                # This file
```

---

## How Matching Works

The matching engine runs a **two-pass** algorithm:

### Pass 1 — Hard Filter
Rejects candidates who don't meet the minimum experience requirement:
```
candidate.years_of_experience >= job.required_experience_years
```

### Pass 2 — Scoring (0-100%)
Combines two signals with configurable weights:

| Signal | Weight | How It Works |
|--------|--------|-------------|
| **Semantic Similarity** | 60% | Cosine similarity between resume & job 384-dim embedding vectors |
| **Skill Overlap** | 40% | `matched_skills / total_required_skills × 100` |

**Final Score** = `semantic × 0.6 + skills × 0.4`

When embeddings are missing (mock mode), semantic similarity defaults to 50%.

---

## Resume Processing Pipeline

```
Upload PDF ──▶ Save to disk ──▶ Create DB record (status: pending)
                                        │
                                  Background Task
                                        │
                        ┌───────────────┼───────────────┐
                        ▼               ▼               ▼
                  Extract text    Parse resume    Generate embedding
                  (pdfplumber)    (regex parser)  (SentenceTransformer
                        │         extracts:        or mock 384-dim)
                        │         • name            │
                        │         • experience      │
                        │         • skills          │
                        │         • title           │
                        └───────────────┼───────────────┘
                                        ▼
                              Update DB (status: ready)
```

### Regex Parser (Local Mode)
Instead of a hardcoded mock, the parser now does lightweight extraction:
- **Experience**: Finds patterns like `"5+ years of experience"` or calculates from date ranges (`2019-2024`)
- **Skills**: Matches against a 60+ skill dictionary (Python, Java, AWS, Docker, etc.)
- **Name**: Extracts from the first line if it matches a name pattern
- **Title**: Finds common job titles in the text

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SQLITE` | `false` | Use SQLite instead of PostgreSQL |
| `USE_MOCK_EMBEDDINGS` | `false` | Use random vectors instead of real model |
| `DB_HOST` | `postgres` | PostgreSQL hostname |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `job_matching_db` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `UPLOAD_DIR` | `/data/uploads` | File upload directory |
| `MAX_FILE_SIZE_MB` | `10` | Max upload size |
| `SCRAPER_API_KEY` | `change-me-in-production` | Webhook auth key |
| `SEMANTIC_WEIGHT` | `0.6` | Matching: semantic score weight |
| `SKILL_WEIGHT` | `0.4` | Matching: skill overlap weight |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace model |
| `EMBEDDING_DIMENSION` | `384` | Vector dimension |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Production Deployment (Docker)

```bash
# Build & run the full stack
docker-compose up --build -d

# This starts 4 containers:
# job-api      → FastAPI (port 8000)
# job-worker   → Celery worker
# job-postgres → PostgreSQL 16 + pgvector (port 5432)
# job-redis    → Redis 7 (port 6379)

# View logs
docker-compose logs -f api worker
```

---

## Frontend Features

| Feature | Description |
|---------|-------------|
| **Browse All Jobs** | View all recent jobs without uploading a resume |
| **Resume Upload** | Drag-and-drop PDF upload with validation |
| **Smart Filters** | Experience slider, location, work model, tech stack, job boards |
| **Processing Progress** | Real-time stepper showing upload → parse → embed → ready |
| **Match Results** | Ranked results with score badges, grouped by source |
| **Apply Links** | Direct links to real job posting pages |
| **Dark Theme** | Premium glassmorphism UI with animations |
| **Error Handling** | Dismissible error banners, graceful fallbacks |

---

## Known Limitations

- **Mock Parser**: The regex parser is a lightweight fallback. For production accuracy, integrate OpenAI/Gemini (see `app/services/parsing.py` integration point).
- **Mock Embeddings**: Random vectors produce ~50% similarity scores. Real model download (~90MB) gives meaningful semantic matching.
- **SQLite**: Good for development but doesn't support true pgvector cosine distance queries. Use PostgreSQL for production.
- **Database Resets**: SQLite DB is deleted on each server restart in the current dev workflow. Use persistent storage or PostgreSQL for data durability.
