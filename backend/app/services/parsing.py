"""
Résumé parsing: PDF text extraction + structured extraction.

Two parsers behind one schema:
  - "gemini": LLM structured extraction (Gemini Flash with a JSON response
    schema) — understands any résumé layout, real skills/titles/dates.
  - "regex": deterministic keyword/pattern parser — offline fallback used in
    tests/CI and whenever the LLM call fails (parsing degrades gracefully;
    unlike embeddings there is no cross-provider poisoning concern).

``parsed_data["parser"]`` records which one produced the result.
"""
import json
import logging
import re
from pathlib import Path

from app.services.skills import categorize_skills, extract_skills

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    if not Path(file_path).exists():
        raise ValueError(f"File not found: {file_path}")

    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

    full_text = "\n".join(pages)
    if not full_text.strip():
        logger.warning("No text extracted from %s", file_path)
    return full_text


def _extract_experience_years(text: str) -> int:
    text_lower = text.lower()
    patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
        r"experience\s*(?:of\s+)?(\d+)\+?\s*(?:years?|yrs?)",
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:in|of)\s*(?:software|development|engineering)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            return max(int(m) for m in matches)

    # No explicit statement — estimate from employment date ranges. Overlapping
    # ranges are MERGED before summing so two parallel roles ("2020–2023" at a
    # job + "2021–2022" freelancing) don't double-count the same years.
    from datetime import datetime, timezone

    this_year = datetime.now(timezone.utc).year
    year_ranges = re.findall(r"(20\d{2})\s*[-–—]\s*(20\d{2}|present|current|now)", text_lower)
    intervals: list[tuple[int, int]] = []
    for start, end in year_ranges:
        end_year = this_year if end in ("present", "current", "now") else int(end)
        if end_year >= int(start):
            intervals.append((int(start), end_year))
    if intervals:
        intervals.sort()
        merged: list[list[int]] = [list(intervals[0])]
        for s, e in intervals[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        total = sum(e - s for s, e in merged)
        if total > 0:
            return min(total, 30)
    # Nothing found → 0 (a fresher résumé must not get phantom years, which
    # would loosen the eligibility hard filter).
    return 0


def _extract_skills(text: str) -> list[dict]:
    """Skills grouped into the parser's category shape, via the shared vocabulary."""
    return categorize_skills(extract_skills(text, limit=40))


def _extract_name(text: str) -> str:
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if lines and re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$", lines[0]):
        return lines[0]
    return "Extracted Name"


# ── LLM structured extraction (Gemini Flash) ────────────────────────────────

_MAX_PARSE_CHARS = 15_000  # plenty for a résumé, bounded for the token budget

# Gemini structured-output schema (OpenAPI subset). The response is forced to
# this shape, so downstream consumers see the exact same dict the regex parser
# produces.
_PARSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "full_name": {"type": "STRING"},
        "current_title": {"type": "STRING"},
        "total_years_experience": {"type": "NUMBER"},
        "technical_skills": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "category": {"type": "STRING"},
                    "skills": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["category", "skills"],
            },
        },
        "domain_expertise": {"type": "ARRAY", "items": {"type": "STRING"}},
        "education": {"type": "ARRAY", "items": {"type": "STRING"}},
        "certifications": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["current_title", "total_years_experience", "technical_skills"],
}

_PARSE_PROMPT = """You are an expert technical recruiter parsing a résumé.
Extract the candidate's profile precisely from the résumé text below.

Rules:
- total_years_experience: total professional (non-internship) years; if not
  stated explicitly, estimate from employment dates. Use 0 for freshers.
- technical_skills: only technologies/tools actually mentioned, grouped into
  short categories (e.g. Languages, Frameworks, Infrastructure, Data). Use
  canonical names (e.g. "PostgreSQL" not "postgres").
- domain_expertise: 2-5 short domain areas evident from the work history
  (e.g. "Backend", "Distributed Systems", "Fintech").
- education: one line per degree ("B.Tech Computer Science, IIT Delhi, 2021").
- Leave anything not present in the résumé empty rather than guessing.

RÉSUMÉ TEXT:
"""


def _parse_with_gemini(raw_text: str) -> dict:
    from app.core.config import get_settings
    from app.services.gemini import gemini_call

    settings = get_settings()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": _PARSE_PROMPT + raw_text[:_MAX_PARSE_CHARS]}],
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _PARSE_SCHEMA,
            "temperature": 0.1,
        },
    }
    data = gemini_call(f"models/{settings.GEMINI_PARSE_MODEL}:generateContent", payload)
    parsed = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    return _clean_llm_parse(parsed)


def _clean_llm_parse(parsed: dict) -> dict:
    """Defensive normalisation of the model output into the canonical schema."""
    def str_list(value) -> list[str]:
        return [str(v).strip() for v in (value or []) if str(v).strip()]

    skills_out: list[dict] = []
    seen: set[str] = set()
    for cat in parsed.get("technical_skills") or []:
        if not isinstance(cat, dict):
            continue
        names = [s for s in str_list(cat.get("skills")) if s.lower() not in seen]
        seen.update(s.lower() for s in names)
        if names:
            skills_out.append({
                "category": str(cat.get("category") or "Other").strip()[:40],
                "skills": names[:30],
            })
    if not skills_out:
        skills_out = [{"category": "General", "skills": ["Software Development"]}]

    try:
        years = max(0, min(50, int(round(float(parsed.get("total_years_experience") or 0)))))
    except (TypeError, ValueError):
        years = 0

    return {
        "full_name": str(parsed.get("full_name") or "").strip() or "Candidate",
        "current_title": str(parsed.get("current_title") or "").strip() or "Software Engineer",
        "total_years_experience": years,
        "technical_skills": skills_out,
        "domain_expertise": str_list(parsed.get("domain_expertise"))[:6],
        "education": str_list(parsed.get("education"))[:6],
        "certifications": str_list(parsed.get("certifications"))[:6],
        "employment_history": [],
        "parser": "gemini",
    }


# ── Dispatcher ───────────────────────────────────────────────────────────────

def parse_resume_text(raw_text: str) -> dict:
    """Parse raw résumé text into a JSON-serialisable structured dict.

    Uses the configured parser; any LLM failure falls back to the regex parser
    so résumé uploads never break on provider issues.
    """
    from app.core.config import get_settings

    logger.info("Parsing résumé text (%d chars)", len(raw_text))
    if get_settings().RESUME_PARSER == "gemini":
        try:
            return _parse_with_gemini(raw_text)
        except Exception:  # noqa: BLE001
            logger.exception("LLM parse failed — falling back to regex parser")
    return _parse_with_regex(raw_text)


def _parse_with_regex(raw_text: str) -> dict:
    title_match = re.search(
        r"(?:software|senior|junior|lead|principal|staff)?\s*"
        r"(?:engineer|developer|architect|manager|analyst)",
        raw_text.lower(),
    )
    return {
        "full_name": _extract_name(raw_text),
        "current_title": title_match.group(0).strip().title() if title_match else "Software Engineer",
        "total_years_experience": _extract_experience_years(raw_text),
        "technical_skills": _extract_skills(raw_text),
        "domain_expertise": ["Backend", "APIs", "Cloud"],
        "education": [],
        "certifications": [],
        "employment_history": [],
        "parser": "regex",
    }
