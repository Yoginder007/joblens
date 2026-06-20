"""
Skill normalization — maps the many ways a skill is written to one canonical
token, so résumé and job skills match even when spelled differently.

Examples that should all collapse to the same canonical skill:
  "JS", "javascript", "java script"        -> "javascript"
  "k8s", "kube", "kubernetes"              -> "kubernetes"
  "node", "nodejs", "node.js"             -> "node.js"
  "postgres", "psql", "postgresql"        -> "postgresql"
  "golang", "go lang", "go"               -> "go"

Pure module (no DB/IO) so it's trivially unit-testable and reusable by the
matching engine, parser, and ingestion skill extraction.
"""
import re

# Canonical skill -> set of aliases (all lowercase). The canonical key is what
# the UI displays; any alias on the résumé or job collapses to it.
_ALIASES: dict[str, list[str]] = {
    "javascript": ["js", "java script", "ecmascript", "es6", "vanilla js"],
    "typescript": ["ts"],
    "python": ["py", "python3"],
    "go": ["golang", "go lang"],
    "c++": ["cpp", "cplusplus", "c plus plus"],
    "c#": ["csharp", "c sharp", "dotnet", ".net"],
    "node.js": ["node", "nodejs", "node js"],
    "react": ["reactjs", "react.js", "react js"],
    "next.js": ["next", "nextjs", "next js"],
    "vue": ["vuejs", "vue.js"],
    "angular": ["angularjs", "angular.js"],
    "kubernetes": ["k8s", "kube", "kubernetes engine"],
    "docker": ["dockerized", "containers", "containerization"],
    "postgresql": ["postgres", "psql", "postgre", "postgres sql"],
    "mysql": ["my sql"],
    "mongodb": ["mongo"],
    "amazon web services": ["aws", "amazon aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure"],
    "ci/cd": ["cicd", "ci cd", "continuous integration", "continuous delivery"],
    "rest": ["rest api", "restful", "restful api", "rest apis"],
    "graphql": ["graph ql"],
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp"],
    "tensorflow": ["tf"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "spring boot": ["springboot", "spring-boot"],
    "distributed systems": ["distributed computing"],
    "object oriented programming": ["oop", "object-oriented"],
    "data structures": ["dsa", "data structures and algorithms"],
}

# Reverse index: alias/canonical -> canonical, built once at import.
_LOOKUP: dict[str, str] = {}
for _canon, _alts in _ALIASES.items():
    _LOOKUP[_canon] = _canon
    for _a in _alts:
        _LOOKUP[_a] = _canon


def _clean(skill: str) -> str:
    """Lowercase, trim, and collapse separators/whitespace for stable lookup."""
    s = skill.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_skill(skill: str) -> str:
    """Return the canonical form of a single skill (or the cleaned input if
    it isn't a known alias)."""
    cleaned = _clean(skill)
    if cleaned in _LOOKUP:
        return _LOOKUP[cleaned]
    # Try a separator-insensitive variant (e.g. "node-js" -> "node js").
    relaxed = re.sub(r"[._/\-]+", " ", cleaned).strip()
    return _LOOKUP.get(relaxed, cleaned)


def normalize_skills(skills) -> set[str]:
    """Normalize an iterable of skills to a set of canonical tokens."""
    out: set[str] = set()
    for s in skills or []:
        if s:
            out.add(normalize_skill(str(s)))
    return out


def display_name(canonical: str) -> str:
    """Human-friendly label for a canonical skill (acronym-aware)."""
    overrides = {
        "amazon web services": "AWS",
        "google cloud platform": "GCP",
        "microsoft azure": "Azure",
        "ci/cd": "CI/CD",
        "rest": "REST",
        "graphql": "GraphQL",
        "natural language processing": "NLP",
        "object oriented programming": "OOP",
        "data structures": "Data Structures",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "node.js": "Node.js",
        "next.js": "Next.js",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "mysql": "MySQL",
        "kubernetes": "Kubernetes",
        "tensorflow": "TensorFlow",
        "scikit-learn": "scikit-learn",
        "machine learning": "Machine Learning",
        "deep learning": "Deep Learning",
        "spring boot": "Spring Boot",
        "distributed systems": "Distributed Systems",
        "c++": "C++",
        "c#": "C#",
        "go": "Go",
        "react": "React",
        "vue": "Vue",
        "angular": "Angular",
        "docker": "Docker",
        "python": "Python",
    }
    if canonical in overrides:
        return overrides[canonical]
    return canonical.title()


# ── Skill vocabulary + extraction (single source of truth) ───────────────────
# One canonical, display-cased vocabulary used by BOTH the ATS scrapers (to pull
# skills out of job descriptions) and the regex résumé parser. Previously each
# kept its own divergent ``_KNOWN_SKILLS`` list.
KNOWN_SKILLS: list[str] = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "Rust",
    "C++", "C#", "Ruby", "Kotlin", "Swift", "Scala", "PHP", "Perl", "Dart", "SQL",
    # Frameworks (Spring Boot before Spring so the more specific name is preferred)
    "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "Django",
    "FastAPI", "Flask", "Spring Boot", "Spring", "Rails", "Laravel",
    # Infra / cloud
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "Git", "Linux", "CI/CD", "Microservices", "Distributed Systems",
    # Data stores / streaming
    "PostgreSQL", "MySQL", "MongoDB", "DynamoDB", "Redis", "Kafka", "Spark",
    "Elasticsearch", "GraphQL", "REST", "gRPC",
    # ML / data
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "PyTorch",
    "TensorFlow", "Pandas", "NumPy", "Scikit-learn", "Data Structures", "Algorithms",
    # Web / misc
    "HTML", "CSS", "Tailwind", "Bootstrap", "Figma", "Agile", "Scrum",
]

# Category buckets for the parser's grouped output (display-cased to match
# KNOWN_SKILLS). "Golang" collapses to "Go" during extraction, so only "Go" here.
_LANGUAGES = {
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "Ruby", "Kotlin", "Swift", "Scala", "PHP", "Perl", "Dart", "SQL",
}
_FRAMEWORKS = {
    "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "Django",
    "FastAPI", "Flask", "Spring", "Spring Boot", "Rails", "Laravel",
}
_INFRA = {
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "Git", "Linux", "CI/CD", "Kafka", "Redis",
}


def extract_skills(text: str, limit: int = 10) -> list[str]:
    """Pull known technical skills out of free text (word-boundary safe, so "Go"
    never matches inside "Google" and "R" never matches inside a word). Returns
    canonical display names; "Golang" collapses to "Go"."""
    if not text:
        return []
    found: list[str] = []
    for skill in KNOWN_SKILLS:
        if re.search(r"(?<![A-Za-z0-9+#.])" + re.escape(skill) + r"(?![A-Za-z0-9+#])", text, re.I):
            canonical = "Go" if skill == "Golang" else skill
            if canonical not in found:
                found.append(canonical)
    return found[:limit]


def categorize_skills(found: list[str]) -> list[dict]:
    """Group extracted skills into the parser's category shape. Empty input
    yields a single "General" bucket so the schema is always populated."""
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
