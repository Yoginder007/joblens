"""
Résumé parsing: PDF text extraction + lightweight structured extraction.

The regex parser is a deterministic fallback. The clearly-marked integration
point swaps in an LLM (OpenAI/Gemini) without touching callers.
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_KNOWN_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "Ruby", "Kotlin", "Swift", "Scala", "R", "PHP", "Perl", "Dart", "SQL",
    "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "Django",
    "FastAPI", "Flask", "Spring", "Spring Boot", "Rails", "Laravel",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "Git", "Linux", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka",
    "Elasticsearch", "GraphQL", "REST", "gRPC", "CI/CD",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-learn",
    "HTML", "CSS", "Tailwind", "Bootstrap", "Figma",
    "Microservices", "Distributed Systems", "Agile", "Scrum",
]

_LANGUAGES = {
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "Ruby", "Kotlin", "Swift", "Scala", "R", "PHP", "SQL", "Dart",
}
_FRAMEWORKS = {
    "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "Django",
    "FastAPI", "Flask", "Spring", "Spring Boot", "Rails", "Laravel",
}
_INFRA = {
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "Git", "Linux", "CI/CD", "Kafka", "Redis",
}


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

    year_ranges = re.findall(r"(20\d{2})\s*[-–—]\s*(20\d{2}|present|current|now)", text_lower)
    if year_ranges:
        total = 0
        for start, end in year_ranges:
            end_year = 2026 if end in ("present", "current", "now") else int(end)
            total += max(0, end_year - int(start))
        if total > 0:
            return min(total, 30)
    return 2


def _extract_skills(text: str) -> list[dict]:
    text_lower = text.lower()
    found: list[str] = []
    for skill in _KNOWN_SKILLS:
        if skill.lower() in ("go", "r", "c"):
            if re.search(r"\b" + re.escape(skill) + r"\b", text):
                found.append(skill)
        elif skill.lower() in text_lower:
            found.append(skill)

    if not found:
        return [{"category": "General", "skills": ["Software Development"], "proficiency": "Unknown"}]

    languages = [s for s in found if s in _LANGUAGES]
    frameworks = [s for s in found if s in _FRAMEWORKS]
    infra = [s for s in found if s in _INFRA]
    other = [s for s in found if s not in _LANGUAGES | _FRAMEWORKS | _INFRA]

    out: list[dict] = []
    if languages:
        out.append({"category": "Languages", "skills": languages, "proficiency": "Advanced"})
    if frameworks:
        out.append({"category": "Frameworks", "skills": frameworks, "proficiency": "Advanced"})
    if infra:
        out.append({"category": "Infrastructure", "skills": infra, "proficiency": "Intermediate"})
    if other:
        out.append({"category": "Other", "skills": other, "proficiency": "Intermediate"})
    return out


def _extract_name(text: str) -> str:
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if lines and re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$", lines[0]):
        return lines[0]
    return "Extracted Name"


def parse_resume_text(raw_text: str) -> dict:
    """Parse raw résumé text into a JSON-serialisable structured dict.

    Integration point: replace the body with an LLM call that returns the same
    schema, and every caller keeps working unchanged.
    """
    logger.info("Parsing résumé text (%d chars)", len(raw_text))
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
    }
