"""
ATS scrapers.

Each company is configured with its **career-page URL**. From that URL we derive
the ATS board token, call the ATS's public board API, and read back the *real*
per-posting job IDs and per-posting apply URLs. Every job carries a concrete
``job_url`` (a specific posting, never a career-root index) and a ``source_id``
built from the real ATS job ID.

Reality of public APIs (probed 2026-05): only Greenhouse (Postman) and Lever
(CRED) boards and Amazon's search.json return usable data. Workday/custom sites
(Razorpay, D.E. Shaw, Goldman Sachs, PayPal, Visa, Uber, Atlassian) have no
public API, so those use the ``curated`` provider — a small set of real, verified
postings — instead of fabricated links.

Providers are registered in ``_FETCHERS`` and selected per portal via its
``ats`` key. Two kinds: per-company ATS boards (greenhouse/lever/amazon), which
must yield a specific-posting URL, and *aggregators* in ``_AGGREGATOR_ATS``
(``adzuna``, ``apify_linkedin``, ``apify_indeed``) that search by keyword +
location across many companies and return trusted redirect URLs. The Apify
portals (real LinkedIn / Indeed postings) activate when ``APIFY_TOKEN`` is set;
Adzuna when its keys are set. Multiple sources run side by side so coverage
compounds.

Pure helpers (``extract_board_token``, ``extract_job_id_from_url``,
``extract_skills``, ``_apify_map``) do parsing and are unit-tested without
network access.
"""
import hashlib
import html
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.services.skills import extract_skills  # re-exported: canonical skill extraction

logger = logging.getLogger(__name__)

# Max postings fetched per live source per ingest run.
_MAX_PER_SOURCE = 100

# Company → config. ``ats`` selects the fetcher; ``url`` is the canonical career
# page (the source of the board token). ``careers_url`` is the human landing page
# surfaced on the home page.
CAREER_PAGES: dict[str, dict[str, str]] = {
    "Postman":        {"ats": "greenhouse", "url": "https://boards.greenhouse.io/postman",  "careers_url": "https://www.postman.com/company/careers/"},
    "CRED":           {"ats": "lever",      "url": "https://jobs.lever.co/cred",            "careers_url": "https://careers.cred.club/"},
    "Amazon":         {"ats": "amazon",     "url": "https://www.amazon.jobs",               "careers_url": "https://www.amazon.jobs/en/"},
    "Adzuna":         {"ats": "adzuna",     "url": "",                                       "careers_url": "https://www.adzuna.in/"},
    # Apify marketplace aggregators — real LinkedIn / Indeed postings (need APIFY_TOKEN):
    "LinkedIn":       {"ats": "apify_linkedin", "url": "", "careers_url": "https://www.linkedin.com/jobs/"},
    "Indeed":         {"ats": "apify_indeed",   "url": "", "careers_url": "https://www.indeed.com/"},
    # Big tech with live Greenhouse boards:
    "Stripe":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/stripe",    "careers_url": "https://stripe.com/jobs"},
    "Databricks":     {"ats": "greenhouse", "url": "https://boards.greenhouse.io/databricks", "careers_url": "https://www.databricks.com/company/careers"},
    "Airbnb":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/airbnb",     "careers_url": "https://careers.airbnb.com/"},
    # Big tech without a public API — served via curated real postings:
    "Microsoft":      {"ats": "curated", "url": "", "careers_url": "https://careers.microsoft.com/"},
    "Google":         {"ats": "curated", "url": "", "careers_url": "https://www.google.com/about/careers/"},
    "Apple":          {"ats": "curated", "url": "", "careers_url": "https://jobs.apple.com/"},
    "Meta":           {"ats": "curated", "url": "", "careers_url": "https://www.metacareers.com/"},
    "Netflix":        {"ats": "curated", "url": "", "careers_url": "https://jobs.netflix.com/"},
    "NVIDIA":         {"ats": "curated", "url": "", "careers_url": "https://www.nvidia.com/en-us/about-nvidia/careers/"},
    # No public API — served via curated real postings:
    "Uber":           {"ats": "curated", "url": "", "careers_url": "https://www.uber.com/careers/"},
    "PayPal":         {"ats": "curated", "url": "", "careers_url": "https://careers.pypl.com/"},
    "D.E. Shaw & Co.": {"ats": "curated", "url": "", "careers_url": "https://www.deshaw.com/careers/"},
    "Goldman Sachs":  {"ats": "curated", "url": "", "careers_url": "https://www.goldmansachs.com/careers"},
    "Razorpay":       {"ats": "curated", "url": "", "careers_url": "https://razorpay.com/jobs/"},
    "Visa":           {"ats": "curated", "url": "", "careers_url": "https://www.visa.com/careers"},
    "Atlassian":      {"ats": "curated", "url": "", "careers_url": "https://www.atlassian.com/company/careers/all-jobs"},
}

# ── Pure helpers (no network) ───────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_experience_years(text: str) -> int:
    if not text:
        return 0
    m = re.findall(r"(\d+)\+?\s*years?", text.lower())
    return min((int(x) for x in m), default=0)


def extract_board_token(career_url: str) -> str | None:
    if not career_url:
        return None
    parts = [p for p in urlparse(career_url).path.split("/") if p]
    if not parts:
        return None
    token = parts[0].lower()
    if token in ("global", "en", "careers", "company", "embed"):
        return None
    return token


def extract_job_id_from_url(job_url: str) -> str | None:
    if not job_url:
        return None
    parsed = urlparse(job_url)
    
    # 1. Check query parameters first (e.g. Stripe, Databricks ?gh_jid=...)
    from urllib.parse import parse_qs
    if parsed.query:
        params = parse_qs(parsed.query)
        for key, vals in params.items():
            for val in vals:
                if val.isdigit() or re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{20,}", val):
                    return val

    # 2. Check path segments
    path = parsed.path.rstrip("/")
    if not path:
        return None
    segments = [p for p in path.split("/") if p]
    if not segments:
        return None
    m = re.search(r"/(?:jobs|list|postings|position)/(\d+)", path)
    if m:
        return m.group(1)
    last = segments[-1]
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{20,}", last):
        return last
    for seg in reversed(segments):
        if seg.isdigit():
            return seg
    return None


# ── Network validity check ──────────────────────────────────────────────────

def _live_checks_enabled() -> bool:
    s = get_settings()
    if s.ENVIRONMENT == "local" or s.EMBEDDING_PROVIDER == "deterministic":
        return False
    return s.VERIFY_JOB_URLS


def is_valid_job_url(url: str) -> bool:
    """True if ``url`` points at a specific posting (and, when live checks are
    enabled, actually resolves). Career-root pages with no posting id are rejected."""
    if not url or extract_job_id_from_url(url) is None:
        return False
    if not _live_checks_enabled():
        return True
    try:
        resp = httpx.head(url, timeout=6.0, follow_redirects=True)
        if resp.status_code in (403, 405):
            resp = httpx.get(url, timeout=6.0, follow_redirects=True)
        if resp.status_code >= 400:
            logger.warning("Dropping dead job URL (%s): %s", resp.status_code, url)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("URL verification failed, dropping %s: %s", url, exc)
        return False


# ── Per-ATS fetchers ─────────────────────────────────────────────────────────

def _greenhouse(company: str, career_url: str) -> list[dict[str, Any]]:
    token = extract_board_token(career_url)
    if not token:
        return []
    out: list[dict[str, Any]] = []
    try:
        r = httpx.get(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
            params={"content": "true"}, timeout=12.0,
        )
        if r.status_code == 200:
            for job in r.json().get("jobs", [])[:_MAX_PER_SOURCE]:
                job_url = job.get("absolute_url")
                job_id = str(job.get("id")) or extract_job_id_from_url(job_url or "")
                desc = strip_html(job.get("content") or "")
                out.append({
                    "title": job.get("title"),
                    "company": company,
                    "description": desc[:1500] or "See full posting for details.",
                    "technical_skills": extract_skills(desc),
                    "required_experience_years": extract_experience_years(desc),
                    "location": (job.get("location") or {}).get("name", "Remote"),
                    "job_url": job_url,
                    "source_id": f"GH-{token}-{job_id}",
                })
    except Exception as exc:  # noqa: BLE001
        logger.error("Greenhouse error for %s: %s", company, exc)
    return out


def _lever(company: str, career_url: str) -> list[dict[str, Any]]:
    token = extract_board_token(career_url)
    if not token:
        return []
    out: list[dict[str, Any]] = []
    try:
        r = httpx.get(f"https://api.lever.co/v0/postings/{token}?mode=json", timeout=12.0)
        if r.status_code == 200:
            for job in r.json()[:_MAX_PER_SOURCE]:
                job_url = job.get("hostedUrl")
                job_id = job.get("id") or extract_job_id_from_url(job_url or "")
                desc = strip_html(job.get("descriptionPlain") or job.get("description") or "")
                out.append({
                    "title": job.get("text"),
                    "company": company,
                    "description": desc[:1500] or "See full posting for details.",
                    "technical_skills": extract_skills(desc),
                    "required_experience_years": extract_experience_years(desc),
                    "location": (job.get("categories") or {}).get("location", "Remote"),
                    "job_url": job_url,
                    "source_id": f"LV-{token}-{job_id}",
                })
    except Exception as exc:  # noqa: BLE001
        logger.error("Lever error for %s: %s", company, exc)
    return out


# Major Indian tech hubs to query individually — the API's global "recent" sort
# is Bengaluru/Hyderabad-heavy, so without per-city queries other cities never
# surface. Each city is fetched separately and results are merged + deduped.
_INDIA_CITIES = [
    "Bengaluru", "Hyderabad", "Pune", "Chennai", "Delhi",
    "Noida", "Gurgaon", "Mumbai", "Kolkata",
]


def _amazon(company: str, career_url: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_city = max(10, _MAX_PER_SOURCE // len(_INDIA_CITIES))
    try:
        for city in _INDIA_CITIES:
            r = httpx.get(
                "https://www.amazon.jobs/en/search.json",
                params={
                    "result_limit": per_city, "sort": "recent",
                    "country": "IND", "city": city,
                    "category[]": "Software Development",
                },
                timeout=12.0,
            )
            if r.status_code != 200:
                continue
            for job in r.json().get("jobs", []):
                jid = str(job.get("id_icims") or job.get("id") or "")
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                desc = strip_html(job.get("description") or "")
                quals = strip_html(job.get("basic_qualifications") or "")
                out.append({
                    "title": (job.get("title") or "").strip(),
                    "company": company,
                    "description": (desc or "Amazon role.")[:1500],
                    "technical_skills": extract_skills(desc + " " + quals),
                    "required_experience_years": extract_experience_years(quals),
                    "location": job.get("normalized_location", f"{city}, India"),
                    "job_url": f"https://www.amazon.jobs{job.get('job_path', '')}",
                    "source_id": f"AMZ-{jid}",
                })
    except Exception as exc:  # noqa: BLE001
        logger.error("Amazon error for %s: %s", company, exc)
    return out[:_MAX_PER_SOURCE]


# Curated REAL postings for companies without a public API live in
# ``curated_jobs.json`` (company -> list of postings) — kept as data, not code.
# URLs are specific, verified postings (not fabricated ids).
_CURATED_PATH = Path(__file__).with_name("curated_jobs.json")


@lru_cache(maxsize=1)
def _curated_data() -> dict[str, list[dict[str, Any]]]:
    return json.loads(_CURATED_PATH.read_text(encoding="utf-8"))


def _curated(company: str, career_url: str) -> list[dict[str, Any]]:
    # Fresh dicts so downstream mutation is isolated from the cached data.
    return [dict(j) for j in _curated_data().get(company, [])]


def _adzuna(company: str, career_url: str) -> list[dict[str, Any]]:
    """Adzuna aggregator — thousands of cross-company jobs. No-op without keys."""
    settings = get_settings()
    if not settings.adzuna_enabled:
        logger.info("Adzuna disabled (no API keys configured)")
        return []
    out: list[dict[str, Any]] = []
    per_page = 50
    try:
        for page in range(1, (_MAX_PER_SOURCE // per_page) + 1):
            r = httpx.get(
                f"https://api.adzuna.com/v1/api/jobs/{settings.ADZUNA_COUNTRY}/search/{page}",
                params={
                    "app_id": settings.ADZUNA_APP_ID,
                    "app_key": settings.ADZUNA_APP_KEY,
                    "results_per_page": per_page,
                    "what": "software engineer",
                    "content-type": "application/json",
                },
                timeout=12.0,
            )
            if r.status_code != 200:
                break
            results = r.json().get("results", [])
            if not results:
                break
            for job in results:
                desc = strip_html(job.get("description") or "")
                out.append({
                    "title": (job.get("title") or "").strip(),
                    "company": (job.get("company") or {}).get("display_name") or "Unknown",
                    "description": (desc or "See full posting.")[:1500],
                    "technical_skills": extract_skills(desc),
                    "required_experience_years": extract_experience_years(desc),
                    "location": (job.get("location") or {}).get("display_name") or "India",
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max"),
                    "job_url": job.get("redirect_url"),
                    "source_id": f"ADZ-{job.get('id')}",
                })
            if len(results) < per_page:
                break
    except Exception as exc:  # noqa: BLE001
        logger.error("Adzuna error: %s", exc)
    return out[:_MAX_PER_SOURCE]


# ── Apify marketplace scrapers (LinkedIn / Indeed) ───────────────────────────
# Apify actors are query-based aggregators (search by keyword + location across
# many companies), not per-company ATS boards. One run-token enables them and
# each returns real posting URLs. Actor input schemas differ, so we send a
# permissive default (synonym keys most actors recognise; extras are ignored)
# and allow a per-portal JSON override for whichever actor you choose.

_APIFY_BASE = "https://api.apify.com/v2/acts"


def _first(item: dict, keys: tuple[str, ...]):
    for k in keys:
        v = item.get(k)
        if v:
            return v
    return None


def _apify_default_input(settings) -> dict:
    q, loc, n = settings.APIFY_SEARCH_QUERY, settings.APIFY_SEARCH_LOCATION, settings.APIFY_MAX_ITEMS
    return {
        "title": q, "position": q, "keyword": q, "keywords": q, "query": q, "search": q,
        "location": loc, "country": loc,
        "maxItems": n, "rows": n, "limit": n, "maxResults": n,
    }


def _run_apify_actor(actor_id: str, run_input: dict) -> list[dict]:
    """Run an actor synchronously and return its dataset items. Network/actor
    errors yield [] so one bad source never breaks the whole ingest run."""
    settings = get_settings()
    try:
        r = httpx.post(
            f"{_APIFY_BASE}/{actor_id}/run-sync-get-dataset-items",
            params={"token": settings.APIFY_TOKEN},
            json=run_input,
            timeout=120.0,
        )
        if r.status_code >= 400:
            logger.error("Apify actor %s failed (%s): %s", actor_id, r.status_code, r.text[:200])
            return []
        data = r.json()
        return data if isinstance(data, list) else data.get("items", [])
    except Exception as exc:  # noqa: BLE001
        logger.error("Apify actor %s error: %s", actor_id, exc)
        return []


def _apify_map(item: dict, source_prefix: str) -> dict[str, Any] | None:
    """Map a single Apify dataset item to our job dict, tolerating the differing
    field names used by various LinkedIn/Indeed actors."""
    title = _first(item, ("title", "positionName", "jobTitle", "position"))
    if not title:
        return None
    url = _first(item, ("jobUrl", "url", "link", "applyUrl", "jobLink"))
    company = _first(item, ("companyName", "company", "employer", "organization"))
    if isinstance(company, dict):
        company = company.get("name") or company.get("displayName") or "Unknown"
    location = _first(item, ("location", "jobLocation", "place", "city")) or "India"
    if isinstance(location, dict):
        location = location.get("displayName") or location.get("name") or "India"
    desc = strip_html(str(_first(item, ("description", "descriptionText", "jobDescription", "snippet")) or ""))

    jid = _first(item, ("id", "jobId", "jobkey", "key")) or extract_job_id_from_url(url or "")
    if not jid and url:
        # Stable fallback id (NOT Python hash(), which is per-process randomised)
        # so re-ingesting the same posting upserts instead of duplicating.
        jid = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    if not jid:
        return None

    salary = item.get("salary") if isinstance(item.get("salary"), dict) else {}
    return {
        "title": str(title).strip(),
        "company": str(company or "Unknown").strip(),
        "description": (desc or "See full posting for details.")[:1500],
        "technical_skills": extract_skills(desc),
        "required_experience_years": extract_experience_years(desc),
        "location": str(location),
        "salary_min": item.get("salaryMin") or salary.get("min"),
        "salary_max": item.get("salaryMax") or salary.get("max"),
        "job_url": url,
        "source_id": f"{source_prefix}-{jid}",
    }


def _apify_fetch(actor_id: str, input_override: str, source_prefix: str) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.apify_enabled:
        logger.info("Apify disabled (no APIFY_TOKEN configured)")
        return []
    if not actor_id:
        return []
    run_input = _apify_default_input(settings)
    if input_override:
        try:
            run_input = json.loads(input_override)
        except json.JSONDecodeError:
            logger.warning("Invalid Apify input override JSON for %s; using default", actor_id)
    out: list[dict[str, Any]] = []
    for item in _run_apify_actor(actor_id, run_input)[:settings.APIFY_MAX_ITEMS]:
        mapped = _apify_map(item, source_prefix)
        if mapped:
            out.append(mapped)
    logger.info("Apify %s: %d postings", actor_id, len(out))
    return out


def _apify_linkedin(company: str, career_url: str) -> list[dict[str, Any]]:
    s = get_settings()
    return _apify_fetch(s.APIFY_LINKEDIN_ACTOR, s.APIFY_LINKEDIN_INPUT, "LI")


def _apify_indeed(company: str, career_url: str) -> list[dict[str, Any]]:
    s = get_settings()
    return _apify_fetch(s.APIFY_INDEED_ACTOR, s.APIFY_INDEED_INPUT, "IND")


_FETCHERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "amazon": _amazon,
    "adzuna": _adzuna,
    "apify_linkedin": _apify_linkedin,
    "apify_indeed": _apify_indeed,
    "curated": _curated,
}

# ATS keys whose URLs are trusted aggregator redirects (no parseable posting id
# required); per-company ATS fetchers must still yield a specific-posting URL.
_AGGREGATOR_ATS = {"curated", "adzuna", "apify_linkedin", "apify_indeed"}

# ATS keys that bill per run (Apify pay-per-result). Scheduled weekly — not
# daily — and gated by the scrape-cadence guard in ``ingest_all``.
_PAID_ATS = {"apify_linkedin", "apify_indeed"}


def companies_by_tier(tier: str = "all") -> list[str]:
    """Portal names by cost tier: 'free' (ATS / Adzuna / curated), 'paid'
    (Apify pay-per-result), or 'all'."""
    if tier == "paid":
        return [n for n, c in CAREER_PAGES.items() if c["ats"] in _PAID_ATS]
    if tier == "free":
        return [n for n, c in CAREER_PAGES.items() if c["ats"] not in _PAID_ATS]
    return list(CAREER_PAGES.keys())


def _normalize(company: str, job: dict[str, Any], require_real_url: bool) -> dict[str, Any] | None:
    """Tag work-model/industry and validate the URL. ``require_real_url`` enforces
    a specific-posting URL (live APIs); curated entries may link to a career root."""
    if not job.get("title"):
        return None
    url = job.get("job_url", "")
    if require_real_url and not is_valid_job_url(url):
        logger.warning("Discarding %s — invalid/dead URL: %s", job.get("source_id"), url)
        return None

    loc = (job.get("location") or "").lower()
    is_remote = "remote" in loc or "distributed" in loc or "anywhere" in loc
    job["is_remote"] = is_remote
    job["work_model"] = "remote" if is_remote else ("hybrid" if "hybrid" in loc else "on-site")
    job.setdefault("technical_skills", [])
    job.setdefault("required_experience_years", 0)
    job["company_size"] = "1000+"
    job["job_type"] = "full-time"
    job["industry"] = "Tech"
    return job


def run_scraper_for_company(company_name: str) -> list[dict[str, Any]]:
    """Fetch postings for one company via its configured provider.

    Live providers (greenhouse/lever/amazon) require a real specific-posting URL;
    curated entries are allowed to point at the company career page.
    """
    cfg = CAREER_PAGES.get(company_name)
    if not cfg:
        logger.warning("No career page configured for %s", company_name)
        return []
    fetch = _FETCHERS.get(cfg["ats"], _curated)
    # Curated + aggregator URLs are trusted redirects without a parseable posting
    # id; only the per-company ATS fetchers must yield a specific-posting URL.
    require_real_url = cfg["ats"] not in _AGGREGATOR_ATS
    out: list[dict[str, Any]] = []
    for job in fetch(company_name, cfg.get("url", "")):
        normalized = _normalize(company_name, job, require_real_url=require_real_url)
        if normalized:
            out.append(normalized)
    return out


def available_portals() -> list[dict[str, Any]]:
    """Portal directory for the UI (name, careers URL, whether it's live)."""
    return [
        {
            "company": name,
            "careers_url": cfg["careers_url"],
            "live": cfg["ats"] != "curated",
            "ats": cfg["ats"],
        }
        for name, cfg in CAREER_PAGES.items()
    ]
