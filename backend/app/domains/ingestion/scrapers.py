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
from app.services.roles import classify_role
from app.services.skills import extract_skills  # re-exported: canonical skill extraction

logger = logging.getLogger(__name__)

# Max postings kept per source per ingest run (applied AFTER any location
# allowlist filter, so a global MNC board can't crowd out its India roles).
_MAX_PER_SOURCE = 100

# Substrings that identify India (or India-relevant remote) locations. Used as
# the per-portal ``locations`` allowlist for global MNC boards so only their
# India postings are ingested — the product's focus market.
INDIA_LOCATIONS = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai",
    "mumbai", "gurugram", "gurgaon", "noida", "delhi", "kolkata", "ahmedabad",
]

# Company → config. ``ats`` selects the fetcher; ``url`` is the canonical career
# page (the source of the board token). ``careers_url`` is the human landing page
# surfaced on the home page. ``group`` buckets the portal for the UI
# ("india" | "global" | "aggregator"). Optional ``locations`` is a lowercase
# substring allowlist — postings whose location matches none are dropped
# (verified live boards probed 2026-07).
CAREER_PAGES: dict[str, dict[str, Any]] = {
    # ── Indian companies with live public ATS boards ──
    "PhonePe":        {"ats": "greenhouse", "url": "https://boards.greenhouse.io/phonepe",  "careers_url": "https://www.phonepe.com/careers/", "group": "india"},
    "Paytm":          {"ats": "lever",      "url": "https://jobs.lever.co/paytm",           "careers_url": "https://jobs.lever.co/paytm", "group": "india"},
    "Meesho":         {"ats": "lever",      "url": "https://jobs.lever.co/meesho",          "careers_url": "https://careers.meesho.com/", "group": "india"},
    "Razorpay":       {"ats": "greenhouse", "url": "https://boards.greenhouse.io/razorpaysoftwareprivatelimited", "careers_url": "https://razorpay.com/jobs/", "group": "india"},
    "CRED":           {"ats": "lever",      "url": "https://jobs.lever.co/cred",            "careers_url": "https://careers.cred.club/", "group": "india"},
    "Dream11":        {"ats": "lever",      "url": "https://jobs.lever.co/dreamsports",     "careers_url": "https://www.dreamsports.group/careers/", "group": "india"},
    "Groww":          {"ats": "greenhouse", "url": "https://boards.greenhouse.io/groww",    "careers_url": "https://groww.in/careers", "group": "india"},
    "InMobi":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/inmobi",   "careers_url": "https://www.inmobi.com/company/careers", "group": "india"},
    "Hevo Data":      {"ats": "lever",      "url": "https://jobs.lever.co/hevodata",        "careers_url": "https://hevodata.com/careers/", "group": "india"},
    "HackerRank":     {"ats": "greenhouse", "url": "https://boards.greenhouse.io/hackerrank", "careers_url": "https://www.hackerrank.com/careers", "group": "india"},
    "Fi (epiFi)":     {"ats": "lever",      "url": "https://jobs.lever.co/epifi",           "careers_url": "https://fi.money/careers", "group": "india"},
    "slice":          {"ats": "greenhouse", "url": "https://boards.greenhouse.io/slice",    "careers_url": "https://www.sliceit.com/careers", "group": "india"},
    "Postman":        {"ats": "greenhouse", "url": "https://boards.greenhouse.io/postman",  "careers_url": "https://www.postman.com/company/careers/", "group": "india"},
    # ── Global MNCs with India engineering (India-filtered live boards) ──
    "Amazon":         {"ats": "amazon",     "url": "https://www.amazon.jobs",               "careers_url": "https://www.amazon.jobs/en/", "group": "global"},
    "MongoDB":        {"ats": "greenhouse", "url": "https://boards.greenhouse.io/mongodb",  "careers_url": "https://www.mongodb.com/careers", "group": "global", "locations": INDIA_LOCATIONS},
    "Okta":           {"ats": "greenhouse", "url": "https://boards.greenhouse.io/okta",     "careers_url": "https://www.okta.com/company/careers/", "group": "global", "locations": INDIA_LOCATIONS},
    "Twilio":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/twilio",   "careers_url": "https://www.twilio.com/en-us/company/jobs", "group": "global", "locations": INDIA_LOCATIONS},
    "Elastic":        {"ats": "greenhouse", "url": "https://boards.greenhouse.io/elastic",  "careers_url": "https://www.elastic.co/careers/", "group": "global", "locations": INDIA_LOCATIONS},
    "GitLab":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/gitlab",   "careers_url": "https://about.gitlab.com/jobs/", "group": "global", "locations": INDIA_LOCATIONS + ["remote"]},
    "Cloudflare":     {"ats": "greenhouse", "url": "https://boards.greenhouse.io/cloudflare", "careers_url": "https://www.cloudflare.com/careers/", "group": "global", "locations": INDIA_LOCATIONS},
    "Datadog":        {"ats": "greenhouse", "url": "https://boards.greenhouse.io/datadog",  "careers_url": "https://careers.datadoghq.com/", "group": "global", "locations": INDIA_LOCATIONS},
    "Coinbase":       {"ats": "greenhouse", "url": "https://boards.greenhouse.io/coinbase", "careers_url": "https://www.coinbase.com/careers", "group": "global", "locations": INDIA_LOCATIONS},
    "Stripe":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/stripe",    "careers_url": "https://stripe.com/jobs", "group": "global"},
    "Databricks":     {"ats": "greenhouse", "url": "https://boards.greenhouse.io/databricks", "careers_url": "https://www.databricks.com/company/careers", "group": "global"},
    "Airbnb":         {"ats": "greenhouse", "url": "https://boards.greenhouse.io/airbnb",     "careers_url": "https://careers.airbnb.com/", "group": "global"},
    # ── Aggregators (cross-company; real redirect URLs) ──
    "Adzuna":         {"ats": "adzuna",     "url": "",  "careers_url": "https://www.adzuna.in/", "group": "aggregator"},
    "LinkedIn":       {"ats": "apify_linkedin", "url": "", "careers_url": "https://www.linkedin.com/jobs/", "group": "aggregator"},
    "Indeed":         {"ats": "apify_indeed",   "url": "", "careers_url": "https://www.indeed.com/", "group": "aggregator"},
    # ── Big tech without a public API — curated real postings ──
    "Microsoft":      {"ats": "curated", "url": "", "careers_url": "https://careers.microsoft.com/", "group": "global"},
    "Google":         {"ats": "curated", "url": "", "careers_url": "https://www.google.com/about/careers/", "group": "global"},
    "Apple":          {"ats": "curated", "url": "", "careers_url": "https://jobs.apple.com/", "group": "global"},
    "Meta":           {"ats": "curated", "url": "", "careers_url": "https://www.metacareers.com/", "group": "global"},
    "Netflix":        {"ats": "curated", "url": "", "careers_url": "https://jobs.netflix.com/", "group": "global"},
    "NVIDIA":         {"ats": "curated", "url": "", "careers_url": "https://www.nvidia.com/en-us/about-nvidia/careers/", "group": "global"},
    "Uber":           {"ats": "curated", "url": "", "careers_url": "https://www.uber.com/careers/", "group": "global"},
    "PayPal":         {"ats": "curated", "url": "", "careers_url": "https://careers.pypl.com/", "group": "global"},
    "D.E. Shaw & Co.": {"ats": "curated", "url": "", "careers_url": "https://www.deshaw.com/careers/", "group": "global"},
    "Goldman Sachs":  {"ats": "curated", "url": "", "careers_url": "https://www.goldmansachs.com/careers", "group": "global"},
    "Visa":           {"ats": "curated", "url": "", "careers_url": "https://www.visa.com/careers", "group": "global"},
    "Atlassian":      {"ats": "curated", "url": "", "careers_url": "https://www.atlassian.com/company/careers/all-jobs", "group": "global"},
}

# ── Pure helpers (no network) ───────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_experience_years(text: str) -> int:
    """Best-effort required-experience extraction from a posting.

    Prefer mentions in an explicit experience context ("5+ years of experience",
    "3 years of backend experience") and take the MAX of those — "8+ years of
    experience … 2 years with React" is an 8-year role, not a 2-year one.
    Only when no experience-context mention exists, fall back to the smallest
    generic "N years" figure (conservative for eligibility filtering).
    """
    if not text:
        return 0
    t = text.lower()
    ctx = re.findall(
        r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:[\w/-]+\s+){0,4}?(?:experience|exp\b)", t
    )
    nums = [int(x) for x in ctx if int(x) <= 30]
    if nums:
        return max(nums)
    generic = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", t) if int(x) <= 30]
    return min(generic, default=0)


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


# Source-reported schedule/commitment strings → our job_type vocabulary.
# Returns None for unknown — a NULL job_type means "not reported", never a guess.
def _map_job_type(raw: str | None) -> str | None:
    if not raw:
        return None
    r = raw.strip().lower().replace("_", "-").replace(" ", "-")
    if "intern" in r:
        return "internship"
    if "contract" in r or "temporary" in r or "fixed-term" in r:
        return "contract"
    if "part-time" in r:
        return "part-time"
    if "full-time" in r or r == "permanent":
        return "full-time"
    return None


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
            # No slice here: the cap is applied AFTER the per-portal location
            # allowlist (run_scraper_for_company), so India roles deep in a
            # global board aren't cut off before filtering.
            for job in r.json().get("jobs", []):
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
            for job in r.json():  # cap applied post-filter in run_scraper_for_company
                job_url = job.get("hostedUrl")
                job_id = job.get("id") or extract_job_id_from_url(job_url or "")
                desc = strip_html(job.get("descriptionPlain") or job.get("description") or "")
                commitment = ((job.get("categories") or {}).get("commitment") or "").lower()
                out.append({
                    "title": job.get("text"),
                    "company": company,
                    "description": desc[:1500] or "See full posting for details.",
                    "technical_skills": extract_skills(desc),
                    "required_experience_years": extract_experience_years(desc),
                    "location": (job.get("categories") or {}).get("location", "Remote"),
                    "job_type": _map_job_type(commitment),
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
                    "job_type": _map_job_type(job.get("job_schedule_type")),
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


def _adzuna_page(settings, page: int, per_page: int, extra: dict[str, str]) -> list[dict]:
    """One Adzuna search call, scoped to the IT category. Returns raw results."""
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "results_per_page": per_page,
        "category": "it-jobs",  # software/IT focus — the product's market
        "content-type": "application/json",
        **extra,
    }
    r = httpx.get(
        f"https://api.adzuna.com/v1/api/jobs/{settings.ADZUNA_COUNTRY}/search/{page}",
        params=params, timeout=12.0,
    )
    if r.status_code != 200:
        return []
    return r.json().get("results", [])


def _adzuna_map(job: dict) -> dict[str, Any]:
    desc = strip_html(job.get("description") or "")
    return {
        "title": (job.get("title") or "").strip(),
        "company": (job.get("company") or {}).get("display_name") or "Unknown",
        "description": (desc or "See full posting.")[:1500],
        "technical_skills": extract_skills(desc),
        "required_experience_years": extract_experience_years(desc),
        "location": (job.get("location") or {}).get("display_name") or "India",
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "job_type": _map_job_type(job.get("contract_time") or job.get("contract_type")),
        "job_url": job.get("redirect_url"),
        "source_id": f"ADZ-{job.get('id')}",
    }


def _adzuna(company: str, career_url: str) -> list[dict[str, Any]]:
    """Adzuna aggregator — cross-company IT jobs, plus targeted queries for the
    big Indian employers that have no public ATS API (Flipkart, Swiggy, Zomato…).
    No-op without keys."""
    settings = get_settings()
    if not settings.adzuna_enabled:
        logger.info("Adzuna disabled (no API keys configured)")
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_page = 50

    def collect(results: list[dict]) -> None:
        for job in results:
            sid = f"ADZ-{job.get('id')}"
            if sid in seen:
                continue
            seen.add(sid)
            out.append(_adzuna_map(job))

    try:
        # 1. Broad software-engineering sweep.
        for page in range(1, (_MAX_PER_SOURCE // per_page) + 1):
            results = _adzuna_page(settings, page, per_page, {"what": "software engineer"})
            collect(results)
            if len(results) < per_page:
                break
        # 2. Company-targeted queries — reaches Indian employers whose own ATS
        #    has no public API. Their postings surface via Adzuna's redirects.
        for target in settings.adzuna_target_companies:
            collect(_adzuna_page(settings, 1, 25, {"company": target, "what": "engineer"}))
    except Exception as exc:  # noqa: BLE001
        logger.error("Adzuna error: %s", exc)
    return out


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
    """Derive work-model/role tags and validate the URL. ``require_real_url``
    enforces a specific-posting URL (live APIs); curated entries may link to a
    career root.

    Metadata policy: only set what we can actually derive. ``job_type`` stays
    whatever the source reported (possibly None — "unknown", never fabricated);
    the sole inference is "intern" in the title → internship.
    """
    if not job.get("title"):
        return None
    url = job.get("job_url", "")
    if require_real_url and not is_valid_job_url(url):
        logger.warning("Discarding %s — invalid/dead URL: %s", job.get("source_id"), url)
        return None

    title = str(job["title"])
    role = classify_role(title)
    # IT-focus guard: company boards carry sales/legal/HR postings that are
    # noise for a software-jobs product — drop them at the door.
    if role == "Other" and get_settings().INGEST_TECH_ONLY:
        return None

    loc = (job.get("location") or "").lower()
    is_remote = "remote" in loc or "distributed" in loc or "anywhere" in loc
    job["is_remote"] = is_remote
    job["work_model"] = "remote" if is_remote else ("hybrid" if "hybrid" in loc else "on-site")
    job.setdefault("technical_skills", [])
    job.setdefault("required_experience_years", 0)
    job["role_category"] = role
    if not job.get("job_type") and "intern" in title.lower():
        job["job_type"] = "internship"
    return job


# Aggregators return cross-company results (broad sweep + per-company targeted
# queries), so they get a higher cap than a single company's board.
_MAX_PER_AGGREGATOR = 300


def run_scraper_for_company(company_name: str) -> list[dict[str, Any]]:
    """Fetch postings for one company via its configured provider.

    Live providers (greenhouse/lever/amazon) require a real specific-posting URL;
    curated entries are allowed to point at the company career page. A portal's
    optional ``locations`` allowlist drops postings outside the focus market
    BEFORE the per-source cap, so e.g. a 400-job global board still yields all
    of its India roles.
    """
    cfg = CAREER_PAGES.get(company_name)
    if not cfg:
        logger.warning("No career page configured for %s", company_name)
        return []
    fetch = _FETCHERS.get(cfg["ats"], _curated)
    # Curated + aggregator URLs are trusted redirects without a parseable posting
    # id; only the per-company ATS fetchers must yield a specific-posting URL.
    require_real_url = cfg["ats"] not in _AGGREGATOR_ATS
    allowed = cfg.get("locations")
    out: list[dict[str, Any]] = []
    for job in fetch(company_name, cfg.get("url", "")):
        if allowed:
            loc = (job.get("location") or "").lower()
            if not any(tok in loc for tok in allowed):
                continue
        normalized = _normalize(company_name, job, require_real_url=require_real_url)
        if normalized:
            out.append(normalized)
    cap = _MAX_PER_AGGREGATOR if cfg["ats"] in _AGGREGATOR_ATS else _MAX_PER_SOURCE
    return out[:cap]


def available_portals() -> list[dict[str, Any]]:
    """Portal directory for the UI (name, careers URL, group, whether it's live)."""
    return [
        {
            "company": name,
            "careers_url": cfg["careers_url"],
            "live": cfg["ats"] != "curated",
            "ats": cfg["ats"],
            "group": cfg.get("group", "global"),
        }
        for name, cfg in CAREER_PAGES.items()
    ]
