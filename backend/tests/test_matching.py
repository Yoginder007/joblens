"""Unit tests for the pure matching engine + embedding determinism (no DB)."""
from app.domains.matching.service import calculate_match
from app.services.embedding import embed_text


def _resume(years: int, skills: list[str]) -> dict:
    return {
        "total_years_experience": years,
        "technical_skills": [{"category": "x", "skills": skills}],
    }


def test_hard_filter_rejects_underqualified():
    res = calculate_match(_resume(2, ["python"]), "Senior", ["Python"], 5, None, None)
    assert res.hard_filter_passed is False
    assert res.match_score == 0.0


def test_skill_overlap_scoring():
    res = calculate_match(
        _resume(5, ["python", "aws"]), "Backend", ["Python", "AWS", "Go"], 3, None, None
    )
    assert res.hard_filter_passed is True
    assert round(res.skill_match_percentage) == 67  # 2 of 3
    found = {s["skill"] for s in res.matched_skills if s["found_in_resume"]}
    assert found == {"python", "aws"}


def test_no_required_skills_is_perfect_overlap():
    res = calculate_match(_resume(3, ["python"]), "Any", [], 0, None, None)
    assert res.skill_match_percentage == 100.0


def test_embedding_is_deterministic_and_normalised():
    import numpy as np

    a, b = embed_text("staff backend engineer"), embed_text("staff backend engineer")
    assert a == b  # stable across calls (SHA-256 seed, not random hash())
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-5


def test_embedding_handles_numpy_vectors_without_truthiness_error():
    import numpy as np

    vec = np.asarray(embed_text("python aws"), dtype=np.float32)
    res = calculate_match(_resume(5, ["python"]), "Eng", ["Python"], 1, vec, vec)
    assert res.hard_filter_passed is True
    assert res.semantic_similarity > 0
