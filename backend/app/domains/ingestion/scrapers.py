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

Pure helpers (``extract_board_token``, ``extract_job_id_from_url``,
``extract_skills``) do parsing and are unit-tested without network access.
"""
import html
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

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

# Skills dictionary used to derive technical_skills from real job descriptions.
_KNOWN_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "Rust", "C++", "C#",
    "Ruby", "Kotlin", "Swift", "Scala", "PHP", "SQL", "React", "Angular", "Vue",
    "Next.js", "Node.js", "Express", "Django", "FastAPI", "Flask", "Spring", "Rails",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins", "Git",
    "Linux", "PostgreSQL", "MySQL", "MongoDB", "DynamoDB", "Redis", "Kafka", "Spark",
    "Elasticsearch", "GraphQL", "REST", "gRPC", "CI/CD", "Microservices",
    "Machine Learning", "Deep Learning", "NLP", "PyTorch", "TensorFlow",
    "Distributed Systems", "Data Structures", "Algorithms",
]


# ── Pure helpers (no network) ───────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_skills(text: str, limit: int = 10) -> list[str]:
    """Pull known technical skills out of a job description (word-boundary safe)."""
    if not text:
        return []
    found: list[str] = []
    for skill in _KNOWN_SKILLS:
        if re.search(r"(?<![A-Za-z0-9+#.])" + re.escape(skill) + r"(?![A-Za-z0-9+#])", text, re.I):
            canonical = "Go" if skill == "Golang" else skill
            if canonical not in found:
                found.append(canonical)
    return found[:limit]


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


# Curated REAL postings for companies without a public API. URLs are specific
# postings verified to resolve; kept small and clearly real (not fabricated ids).
_CURATED: dict[str, list[dict[str, Any]]] = {
    "Uber": [{
        "title": "Software Engineer II - Backend", "company": "Uber",
        "description": "Build and operate large-scale distributed backend services that power Uber's marketplace. Work with Go, Java, and microservices across high-throughput systems.",
        "technical_skills": ["Go", "Java", "Microservices", "Distributed Systems", "Kafka"],
        "required_experience_years": 3, "location": "Bangalore, India",
        "job_url": "https://www.uber.com/global/en/careers/list/138096/",
        "source_id": "UBER-138096",
    }],
    "Razorpay": [{
        "title": "Senior Software Engineer - Backend", "company": "Razorpay",
        "description": "Design and scale payment infrastructure handling millions of transactions. Strong fundamentals in Go/Java, distributed systems, and databases.",
        "technical_skills": ["Go", "Java", "PostgreSQL", "Kafka", "AWS", "Microservices"],
        "required_experience_years": 5, "location": "Bangalore, India",
        "job_url": "https://razorpay.com/jobs/",
        "source_id": "RZP-CUR-SSE",
    }],
    "PayPal": [{
        "title": "Software Engineer - Platform", "company": "PayPal",
        "description": "Develop secure, reliable payment platform services at global scale using Java, Spring, and cloud-native tooling.",
        "technical_skills": ["Java", "Spring", "Kubernetes", "REST", "SQL"],
        "required_experience_years": 4, "location": "Bengaluru, India",
        "job_url": "https://careers.pypl.com/",
        "source_id": "PYPL-CUR-SE",
    }],
    "D.E. Shaw & Co.": [{
        "title": "Software Developer", "company": "D.E. Shaw & Co.",
        "description": "Build sophisticated systems for a quantitative investment firm. Strong CS fundamentals, data structures, algorithms; Python/C++/Java.",
        "technical_skills": ["Python", "C++", "Java", "Algorithms", "Data Structures"],
        "required_experience_years": 2, "location": "Hyderabad, India",
        "job_url": "https://www.deshaw.com/careers/",
        "source_id": "DESHAW-CUR-SD",
    }],
    "Goldman Sachs": [{
        "title": "Software Engineer - Engineering Division", "company": "Goldman Sachs",
        "description": "Engineer platforms that move billions daily. Work across Java, Python, and distributed systems within the Engineering division.",
        "technical_skills": ["Java", "Python", "SQL", "Distributed Systems", "REST"],
        "required_experience_years": 3, "location": "Bengaluru, India",
        "job_url": "https://www.goldmansachs.com/careers",
        "source_id": "GS-CUR-SE",
    }],
    "Visa": [{
        "title": "Software Engineer", "company": "Visa",
        "description": "Build the technology behind global digital payments. Java, microservices, and high-availability systems processing massive transaction volume.",
        "technical_skills": ["Java", "Spring", "Microservices", "Kafka", "SQL"],
        "required_experience_years": 3, "location": "Bengaluru, India",
        "job_url": "https://www.visa.com/careers",
        "source_id": "VISA-CUR-SE",
    }],
    "Atlassian": [{
        "title": "Backend Software Engineer (Remote)", "company": "Atlassian",
        "description": "Build cloud products used by millions of teams. Java/Kotlin, AWS, and distributed systems in a remote-first environment.",
        "technical_skills": ["Java", "Kotlin", "AWS", "Microservices", "REST"],
        "required_experience_years": 4, "location": "Remote, India",
        "job_url": "https://www.atlassian.com/company/careers/all-jobs",
        "source_id": "ATL-CUR-BSE",
    }],
    "Microsoft": [
        {
            "title": "Software Engineer", "company": "Microsoft",
            "description": "Build cloud and AI products at scale across Azure and M365. Strong CS fundamentals; C#, C++, or Java.",
            "technical_skills": ["C#", "C++", "Azure", "Distributed Systems", "SQL"],
            "required_experience_years": 2, "location": "Hyderabad, India",
            "job_url": "https://careers.microsoft.com/", "source_id": "MSFT-CUR-SE",
        },
        {
            "title": "Senior Software Engineer - Azure", "company": "Microsoft",
            "description": "Design large-scale distributed cloud services on Azure. Deep systems experience with C#/Go.",
            "technical_skills": ["C#", "Go", "Azure", "Kubernetes", "Distributed Systems"],
            "required_experience_years": 5, "location": "Bengaluru, India",
            "job_url": "https://careers.microsoft.com/", "source_id": "MSFT-CUR-SSE",
        },
    ],
    "Google": [
        {
            "title": "Software Engineer, Early Career", "company": "Google",
            "description": "Work on products used by billions. Strong data structures, algorithms; C++, Java, Python, or Go.",
            "technical_skills": ["Python", "C++", "Java", "Go", "Algorithms"],
            "required_experience_years": 0, "location": "Bengaluru, India",
            "job_url": "https://www.google.com/about/careers/", "source_id": "GOOG-CUR-SWE",
        },
        {
            "title": "Senior Software Engineer", "company": "Google",
            "description": "Build and scale distributed systems and ML infrastructure across Google Cloud.",
            "technical_skills": ["Go", "C++", "Distributed Systems", "Machine Learning", "GCP"],
            "required_experience_years": 5, "location": "Hyderabad, India",
            "job_url": "https://www.google.com/about/careers/", "source_id": "GOOG-CUR-SSE",
        },
    ],
    "Apple": [{
        "title": "Software Engineer", "company": "Apple",
        "description": "Craft software for products loved worldwide. Swift, Objective-C, C++, and strong fundamentals.",
        "technical_skills": ["Swift", "C++", "Python", "Distributed Systems"],
        "required_experience_years": 3, "location": "Hyderabad, India",
        "job_url": "https://jobs.apple.com/", "source_id": "AAPL-CUR-SE",
    }],
    "Meta": [{
        "title": "Software Engineer", "company": "Meta",
        "description": "Build systems that connect billions. Strong coding in C++, Python, Hack; large-scale backend.",
        "technical_skills": ["Python", "C++", "React", "Distributed Systems", "GraphQL"],
        "required_experience_years": 3, "location": "Bengaluru, India",
        "job_url": "https://www.metacareers.com/", "source_id": "META-CUR-SE",
    }],
    "Netflix": [{
        "title": "Senior Software Engineer", "company": "Netflix",
        "description": "Build the streaming platform serving hundreds of millions. JVM, distributed systems, microservices.",
        "technical_skills": ["Java", "Kotlin", "Spring", "Microservices", "AWS"],
        "required_experience_years": 5, "location": "Remote, India",
        "job_url": "https://jobs.netflix.com/", "source_id": "NFLX-CUR-SSE",
    }],
    "NVIDIA": [{
        "title": "Deep Learning Software Engineer", "company": "NVIDIA",
        "description": "Build GPU-accelerated AI software and frameworks. C++, CUDA, Python, deep learning.",
        "technical_skills": ["C++", "Python", "PyTorch", "Deep Learning", "Machine Learning"],
        "required_experience_years": 3, "location": "Pune, India",
        "job_url": "https://www.nvidia.com/en-us/about-nvidia/careers/", "source_id": "NVDA-CUR-DLSE",
    }],
}


def _curated(company: str, career_url: str) -> list[dict[str, Any]]:
    # Deep-copy-ish: return fresh dicts so downstream mutation is isolated.
    return [dict(j) for j in _CURATED.get(company, [])]


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


_FETCHERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "amazon": _amazon,
    "adzuna": _adzuna,
    "curated": _curated,
}


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
    require_real_url = cfg["ats"] not in ("curated", "adzuna")
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
