"""
Role taxonomy — maps raw job titles to a fixed set of software-engineering
role categories, so the UI can offer a clean, Amazon-style "Role" facet
instead of 200 raw scraped titles.

Pure module (no DB/IO), mirroring ``skills.py``: trivially unit-testable and
shared by ingestion (tagging at scrape time) and the jobs domain (facet order).

Rules are ordered — the FIRST matching category wins. Specific disciplines
(ML, Data, DevOps…) are checked before the generic buckets, and management is
checked first so "Engineering Manager, Frontend" lands in management, matching
how ATSes (and Amazon's ``is_manager`` facet) treat it.
"""
import re

# Display-ready category names, in the order the UI should present them.
ROLE_CATEGORIES: list[str] = [
    "Backend",
    "Frontend",
    "Full-Stack",
    "Mobile",
    "DevOps / SRE",
    "Data",
    "ML / AI",
    "QA / Testing",
    "Security",
    "Embedded / Systems",
    "Engineering Management",
    "Software Engineering",  # general SE roles that fit no specific discipline
    "Other",                 # non-engineering roles from company boards
]

# (category, compiled pattern) — first match wins. Patterns run on the
# lowercased title. Word boundaries guard short tokens ("qa", "sre", "ai").
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Engineering Management", re.compile(
        r"engineering\s+(manager|director|head|lead(er)?ship)"
        r"|(head|director|vp|vice president)\s+(of\s+)?(engineering|technology)"
        r"|lead,?\s+engineering|engineering\s+lead"
        r"|software\s+(development\s+)?manager|\bsdm\b|tech(nical)?\s+lead\s+manager"
    )),
    ("ML / AI", re.compile(
        r"machine\s*learning|\bml\b|\bai\b|artificial intelligence|deep learning"
        r"|data scien|computer vision|\bnlp\b|\bllm\b|gen(erative)?\s*ai|research (scientist|engineer)"
    )),
    ("Data", re.compile(
        r"data\s+(engineer|platform|infrastructure|architect|analyst|analytics)"
        r"|big data|\betl\b|analytics engineer|business intelligence|\bbi\b"
        r"|database (administrator|engineer)|\bdba\b"
    )),
    ("DevOps / SRE", re.compile(
        r"devops|\bsre\b|site reliability|platform engineer|infrastructure engineer"
        r"|cloud (engineer|architect|operations)|sys(tems)? admin|release engineer"
        r"|build engineer|reliability engineer|production engineer"
    )),
    ("Security", re.compile(
        r"security|appsec|infosec|cyber|penetration|vulnerab|\bsoc\b|threat"
    )),
    ("Mobile", re.compile(
        r"android|\bios\b|mobile|flutter|react native|swift developer|kotlin developer"
    )),
    ("QA / Testing", re.compile(
        r"\bqa\b|\bsdet\b|test(ing)? engineer|quality (assurance|engineer)|automation engineer|\btester\b"
    )),
    ("Full-Stack", re.compile(
        r"full[\s-]?stack|\bmern\b|\bmean\b"
    )),
    ("Frontend", re.compile(
        r"front[\s-]?end|\bui\b (engineer|developer)|web (developer|engineer)"
        r"|react (developer|engineer)|angular (developer|engineer)|javascript (developer|engineer)"
    )),
    ("Backend", re.compile(
        r"back[\s-]?end|server[\s-]?side|api (engineer|developer)"
        r"|(java|python|golang|go|node(\.js)?|ruby|php|\.net|c\+\+) (developer|engineer)"
        r"|microservices"
    )),
    ("Embedded / Systems", re.compile(
        r"embedded|firmware|kernel|\brtos\b|silicon|hardware engineer|systems software"
    )),
    ("Software Engineering", re.compile(
        r"software (engineer|developer|development)|\bsde\b|\bswe\b|\bmts\b"
        r"|member of technical staff|application (engineer|developer)"
        r"|\bdeveloper\b|\bprogrammer\b|solutions? (engineer|architect)"
        r"|technical architect|\bengineer\b"
    )),
]


def classify_role(title: str | None) -> str:
    """Map a raw job title to one taxonomy category ("Other" when nothing fits)."""
    if not title:
        return "Other"
    t = title.lower()
    for category, pattern in _RULES:
        if pattern.search(t):
            return category
    return "Other"


def taxonomy_order(values: list[str]) -> list[str]:
    """Sort role-category values into the canonical taxonomy presentation order."""
    rank = {c: i for i, c in enumerate(ROLE_CATEGORIES)}
    return sorted(values, key=lambda v: (rank.get(v, len(ROLE_CATEGORIES)), v))
