"""Unit tests for skill normalization + alias-aware matching."""
import pytest

from app.domains.matching.service import calculate_match
from app.services.skills import display_name, normalize_skill, normalize_skills


@pytest.mark.parametrize("raw, canonical", [
    ("JS", "javascript"),
    ("javascript", "javascript"),
    ("Java Script", "javascript"),
    ("k8s", "kubernetes"),
    ("Kube", "kubernetes"),
    ("node", "node.js"),
    ("nodejs", "node.js"),
    ("node-js", "node.js"),
    ("postgres", "postgresql"),
    ("psql", "postgresql"),
    ("golang", "go"),
    ("AWS", "amazon web services"),
    ("gcp", "google cloud platform"),
    ("ml", "machine learning"),
    ("Rust", "rust"),            # unknown → cleaned passthrough
])
def test_normalize_skill(raw, canonical):
    assert normalize_skill(raw) == canonical


def test_normalize_skills_dedupes_aliases():
    # JS, javascript, and "java script" all collapse to one token.
    assert normalize_skills(["JS", "javascript", "Java Script", "Python"]) == {
        "javascript", "python",
    }


def test_display_name_acronyms():
    assert display_name("amazon web services") == "AWS"
    assert display_name("javascript") == "JavaScript"
    assert display_name("node.js") == "Node.js"


def _resume(skills: list[str], years: int = 5) -> dict:
    return {"total_years_experience": years, "technical_skills": [{"skills": skills}]}


def test_alias_aware_overlap_counts_synonyms_as_matches():
    # Résumé says "JS" + "k8s"; job wants "JavaScript" + "Kubernetes" → full match.
    res = calculate_match(
        _resume(["JS", "k8s"]), "Backend", ["JavaScript", "Kubernetes"], 1, None, None,
    )
    assert res.skill_match_percentage == 100.0
    found = {s["skill"] for s in res.matched_skills if s["found_in_resume"]}
    assert found == {"JavaScript", "Kubernetes"}


def test_missing_skills_reported_with_canonical_names():
    res = calculate_match(
        _resume(["python"]), "ML role", ["Python", "TensorFlow", "AWS"], 1, None, None,
    )
    missing = {s["skill"] for s in res.matched_skills if not s["found_in_resume"]}
    assert missing == {"TensorFlow", "AWS"}
    assert round(res.skill_match_percentage) == 33  # 1 of 3


def test_reasoning_is_human_readable():
    res = calculate_match(
        _resume(["python", "aws"]), "Eng", ["Python", "AWS", "Go"], 1, None, None,
    )
    assert "skill match" in res.reasoning.lower()
    assert "%" in res.reasoning


def test_duplicate_job_skills_deduped():
    # Job lists "JS" and "javascript" — should count as one required skill.
    res = calculate_match(
        _resume(["javascript"]), "FE", ["JS", "javascript"], 1, None, None,
    )
    assert res.skill_match_percentage == 100.0
    assert len([s for s in res.matched_skills]) == 1


def test_direct_mode_scores_on_skills_only():
    # With no embeddings, semantic falls back to 50%. In semantic mode that
    # drags a 2/2 skill match below 100; in direct mode the score IS the skill %.
    skills_resume = _resume(["python", "aws"])
    semantic = calculate_match(skills_resume, "Eng", ["Python", "AWS"], 1, None, None, match_mode="semantic")
    direct = calculate_match(skills_resume, "Eng", ["Python", "AWS"], 1, None, None, match_mode="direct")
    assert direct.match_score == 100.0          # skill overlap only
    assert semantic.match_score < direct.match_score  # 0.6*50 + 0.4*100 = 70
    assert "skill match" in direct.reasoning.lower()


def test_direct_mode_still_applies_experience_hard_filter():
    # Under-qualified candidate is rejected regardless of mode.
    res = calculate_match(_resume(["python"], years=1), "Senior", ["Python"], 5, None, None, match_mode="direct")
    assert res.hard_filter_passed is False
    assert res.match_score == 0.0
