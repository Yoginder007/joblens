"""
Two-pass matching engine (pure — no DB, no I/O).

Pass 1: hard experience filter.
Pass 2: weighted score = semantic_similarity * W_sem + skill_overlap * W_skill.

All embedding checks are explicit ``is None`` / length tests so the function
behaves identically whether embeddings arrive as Python lists or NumPy arrays
(pgvector returns the latter).
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domains.jobs.repository import JobFilters, JobRepository
from app.domains.jobs.schemas import JobResponse
from app.domains.matching.models import JobMatch
from app.domains.matching.schemas import (
    CompanyMatchGroup,
    EligibleJobSummary,
    EligibleJobsResponse,
    JobMatchResult,
    MatchedSkillDetail,
    MatchesResponse,
)
from app.domains.resumes.models import Resume
from app.services.embedding import cosine_similarity
from app.services.skills import display_name, normalize_skill, normalize_skills

logger = logging.getLogger(__name__)


def _has_vector(v) -> bool:
    return v is not None and len(v) > 0


@dataclass
class MatchResult:
    match_score: float = 0.0
    hard_filter_passed: bool = False
    semantic_similarity: float = 0.0
    skill_match_percentage: float = 0.0
    matched_skills: list[dict] = field(default_factory=list)
    reasoning: str = ""


def calculate_match(
    resume_data: dict,
    job_title: str,
    job_skills: list[str],
    required_experience: int,
    resume_embedding,
    job_embedding,
    cosine_sim: float | None = None,
    match_mode: str = "semantic",
) -> MatchResult:
    """Score one résumé↔job pair.

    ``cosine_sim`` (raw cosine in [-1, 1]) may be supplied by the caller to avoid
    recomputing a similarity the retrieval step already produced (pgvector ANN or
    the SQLite fallback both yield a distance). When ``None``, it's computed here.

    ``match_mode``:
      - "semantic" (default): weighted blend of semantic similarity + skill overlap.
      - "direct": score on skill overlap alone. Useful when the candidate has
        already narrowed by hard filters (location/experience) and just wants
        skill-relevant roles — and avoids letting an approximate semantic signal
        depress the score when job descriptions omit explicit skills.
    """
    settings = get_settings()
    result = MatchResult()
    candidate_years = resume_data.get("total_years_experience", 0) or 0

    # ── Pass 1: hard filter ──
    if candidate_years < required_experience:
        result.reasoning = (
            f"Insufficient experience: {candidate_years}y < required {required_experience}y"
        )
        return result
    result.hard_filter_passed = True

    # ── Pass 2a: semantic ──
    if cosine_sim is not None:
        result.semantic_similarity = max(0.0, (cosine_sim + 1.0) / 2.0 * 100.0)
    elif _has_vector(resume_embedding) and _has_vector(job_embedding):
        raw = cosine_similarity(list(resume_embedding), list(job_embedding))
        result.semantic_similarity = max(0.0, (raw + 1.0) / 2.0 * 100.0)
    else:
        result.semantic_similarity = 50.0  # neutral fallback when embeddings pending

    # ── Pass 2b: skill overlap (alias-aware) ──
    # Normalize both sides to canonical tokens so "JS"/"javascript" or
    # "k8s"/"kubernetes" count as the same skill.
    resume_skills: set[str] = set()
    for cat in resume_data.get("technical_skills", []) or []:
        if isinstance(cat, dict):
            resume_skills |= normalize_skills(cat.get("skills", []))
        elif isinstance(cat, str):
            resume_skills.add(normalize_skill(cat))

    # Preserve the job's required-skill order while deduping by canonical token.
    job_canon: list[str] = []
    seen: set[str] = set()
    for s in job_skills:
        c = normalize_skill(s)
        if c not in seen:
            seen.add(c)
            job_canon.append(c)

    matched = [c for c in job_canon if c in resume_skills]
    missing = [c for c in job_canon if c not in resume_skills]
    result.skill_match_percentage = (
        len(matched) / len(job_canon) * 100 if job_canon else 100.0
    )

    result.matched_skills = [
        {"skill": display_name(c), "found_in_resume": True, "required": True}
        for c in matched
    ]
    result.matched_skills.extend(
        {"skill": display_name(c), "found_in_resume": False, "required": True}
        for c in missing
    )

    # ── Final score ──
    if match_mode == "direct":
        # Skill-overlap only — the candidate has pre-filtered on hard criteria
        # and wants skill relevance, not an approximate semantic guess.
        result.match_score = result.skill_match_percentage
    else:
        result.match_score = (
            result.semantic_similarity * settings.SEMANTIC_WEIGHT
            + result.skill_match_percentage * settings.SKILL_WEIGHT
        )

    # ── Explainability: a plain-English "why this matched" line ──
    if not job_canon:
        skills_note = "no specific skills required"
    elif matched and missing:
        skills_note = (
            f"you have {len(matched)}/{len(job_canon)} required skills "
            f"({', '.join(display_name(c) for c in matched[:3])}"
            f"{'…' if len(matched) > 3 else ''}); "
            f"missing {', '.join(display_name(c) for c in missing[:3])}"
            f"{'…' if len(missing) > 3 else ''}"
        )
    elif matched:
        skills_note = f"you have all {len(matched)} required skills"
    else:
        skills_note = f"none of the {len(job_canon)} required skills found on your résumé"

    if match_mode == "direct":
        result.reasoning = (
            f"{result.match_score:.0f}% skill match ({skills_note}). "
            f"Filtered by your criteria."
        )
    else:
        result.reasoning = (
            f"{result.match_score:.0f}% overall — semantic relevance "
            f"{result.semantic_similarity:.0f}%, skill match "
            f"{result.skill_match_percentage:.0f}% ({skills_note})."
        )
    return result


def _to_skill_details(matched_skills: list[dict]) -> list[MatchedSkillDetail]:
    return [MatchedSkillDetail(**s) for s in matched_skills]


class MatchingService:
    """Orchestrates retrieval + scoring + persistence on top of the pure engine."""

    def __init__(self, db: Session):
        self.db = db
        self.jobs = JobRepository(db)

    def _candidate_exp(self, resume: Resume) -> int:
        return (resume.parsed_data or {}).get("total_years_experience", 0) or 0

    def _upsert_match(self, resume_id, job_id, res: MatchResult) -> None:
        values = dict(
            resume_id=resume_id,
            job_id=job_id,
            match_score=res.match_score,
            hard_filter_passed=res.hard_filter_passed,
            semantic_similarity=res.semantic_similarity,
            skill_match_percentage=res.skill_match_percentage,
            matched_skills=res.matched_skills,
            reasoning=res.reasoning,
        )
        update_cols = (
            "match_score", "hard_filter_passed", "semantic_similarity",
            "skill_match_percentage", "matched_skills", "reasoning",
        )
        if self.db.bind.dialect.name == "postgresql":
            stmt = pg_insert(JobMatch).values(**values).on_conflict_do_update(
                constraint="uq_resume_job_match",
                set_={**{c: values[c] for c in update_cols}, "updated_at": func.now()},
            )
            self.db.execute(stmt)
        else:
            existing = self.db.scalar(
                select(JobMatch).where(
                    JobMatch.resume_id == resume_id, JobMatch.job_id == job_id
                )
            )
            if existing:
                for c in update_cols:
                    setattr(existing, c, values[c])
            else:
                self.db.add(JobMatch(**values))

    def score_candidates(
        self, resume: Resume, filters: JobFilters, limit: int, min_score: float
    ) -> list[tuple]:
        """Return [(Job, MatchResult)] above min_score, nearest-first. No persistence."""
        candidate_exp = self._candidate_exp(resume)
        pairs = self.jobs.nearest(resume.embedding, candidate_exp, filters, limit)
        scored: list[tuple] = []
        for job, dist in pairs:
            # Reuse the retrieval distance instead of recomputing cosine.
            res = calculate_match(
                resume.parsed_data or {}, job.title, job.technical_skills or [],
                job.required_experience_years or 0, resume.embedding, job.embedding,
                cosine_sim=1.0 - dist,
            )
            if res.match_score >= min_score:
                scored.append((job, res))
        return scored

    def run_matches(
        self, resume: Resume, filters: JobFilters, limit: int, min_score: float
    ) -> MatchesResponse:
        companies: dict[str, list[JobMatchResult]] = {}
        flat: list[JobMatchResult] = []
        for job, res in self.score_candidates(resume, filters, limit, min_score):
            item = JobMatchResult(
                job=JobResponse.model_validate(job),
                match_score=res.match_score,
                hard_filter_passed=res.hard_filter_passed,
                semantic_similarity=res.semantic_similarity,
                skill_match_percentage=res.skill_match_percentage,
                matched_skills=_to_skill_details(res.matched_skills),
                reasoning=res.reasoning,
            )
            companies.setdefault(job.company or "Unknown", []).append(item)
            flat.append(item)
            self._upsert_match(resume.id, job.id, res)
        self.db.commit()
        groups = [CompanyMatchGroup(company_name=c, jobs=j) for c, j in companies.items()]
        return MatchesResponse(
            resume_id=resume.id, total_matches=len(flat), companies=groups, matches=flat
        )

    def eligible(
        self, resume: Resume, filters: JobFilters, limit: int, match_mode: str = "semantic"
    ) -> EligibleJobsResponse:
        candidate_exp = self._candidate_exp(resume)
        jobs = self.jobs.eligible(candidate_exp, filters, limit)
        out: list[EligibleJobSummary] = []
        for job in jobs:
            res = calculate_match(
                resume.parsed_data or {}, job.title, job.technical_skills or [],
                job.required_experience_years or 0, resume.embedding, job.embedding,
                match_mode=match_mode,
            )
            out.append(EligibleJobSummary(
                job_id=job.id, title=job.title, company=job.company, location=job.location,
                description=job.description, source=job.source,
                required_experience_years=job.required_experience_years or 0,
                technical_skills=job.technical_skills, job_url=job.job_url,
                match_score=res.match_score, reasoning=res.reasoning,
                semantic_similarity=res.semantic_similarity,
                skill_match_percentage=res.skill_match_percentage,
                matched_skills=_to_skill_details(res.matched_skills),
                work_model=job.work_model, industry=job.industry, job_type=job.job_type,
            ))
        out.sort(key=lambda j: j.match_score, reverse=True)
        return EligibleJobsResponse(
            resume_id=resume.id, candidate_experience_years=candidate_exp,
            total_eligible=len(out), eligible_jobs=out,
        )
