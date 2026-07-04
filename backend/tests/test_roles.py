"""Role-taxonomy classifier tests (pure, no DB/network)."""
import pytest

from app.services.roles import ROLE_CATEGORIES, classify_role, taxonomy_order


@pytest.mark.parametrize("title, expected", [
    # Specific disciplines
    ("Senior Backend Engineer", "Backend"),
    ("Software Engineer - Backend (Payments)", "Backend"),
    ("Java Developer", "Backend"),
    ("Frontend Engineer, Design Systems", "Frontend"),
    ("React Developer", "Frontend"),
    ("Full Stack Developer (React/Node)", "Full-Stack"),
    ("Fullstack Engineer", "Full-Stack"),
    ("Android Engineer", "Mobile"),
    ("iOS Developer", "Mobile"),
    ("Site Reliability Engineer II", "DevOps / SRE"),
    ("DevOps Engineer", "DevOps / SRE"),
    ("Platform Engineer, Kubernetes", "DevOps / SRE"),
    ("Data Engineer - Analytics Platform", "Data"),
    ("Senior Data Analyst", "Data"),
    ("Machine Learning Engineer", "ML / AI"),
    ("Data Scientist, Recommendations", "ML / AI"),
    ("Application Security Engineer", "Security"),
    ("SDET II", "QA / Testing"),
    ("QA Automation Engineer", "QA / Testing"),
    ("Embedded Software Engineer", "Embedded / Systems"),
    ("Firmware Engineer", "Embedded / Systems"),
    # Management outranks discipline (Amazon-style is_manager semantics)
    ("Engineering Manager, Frontend", "Engineering Management"),
    ("Software Development Manager", "Engineering Management"),
    ("Director of Engineering", "Engineering Management"),
    # General SE bucket
    ("Software Development Engineer II, Alexa Devices", "Software Engineering"),
    ("SDE 1", "Software Engineering"),
    ("Member of Technical Staff", "Software Engineering"),
    # Non-engineering roles from company boards
    ("Senior Product Marketing Lead", "Other"),
    ("Talent Acquisition Partner", "Other"),
    ("", "Other"),
    (None, "Other"),
])
def test_classify_role(title, expected):
    assert classify_role(title) == expected


def test_taxonomy_order_is_canonical():
    shuffled = ["Other", "Backend", "ML / AI", "Frontend"]
    assert taxonomy_order(shuffled) == ["Backend", "Frontend", "ML / AI", "Other"]
    # Unknown values sort last, alphabetically, instead of crashing.
    assert taxonomy_order(["Zzz", "Backend"]) == ["Backend", "Zzz"]


def test_all_rule_categories_are_in_taxonomy():
    from app.services.roles import _RULES

    assert {cat for cat, _ in _RULES} <= set(ROLE_CATEGORIES)
