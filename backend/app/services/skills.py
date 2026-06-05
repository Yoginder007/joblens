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
