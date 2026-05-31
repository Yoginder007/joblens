# Launch the API locally with no external services (SQLite + in-process Celery).
# Usage:  cd backend ;  ./run_local.ps1
$env:ENVIRONMENT = "local"
$env:DEBUG = "true"
$env:DATABASE_URL = "sqlite:///./jobmatch_local.db"
$env:EMBEDDING_PROVIDER = "deterministic"
$env:CELERY_TASK_ALWAYS_EAGER = "true"
$env:UPLOAD_DIR = "./uploads"

Write-Host "Starting JobMatch AI (local SQLite profile) on http://localhost:8000/api/docs" -ForegroundColor Cyan
python -m uvicorn app.main:app --reload --port 8000
