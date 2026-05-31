import uuid

from pydantic import BaseModel, ConfigDict

from app.domains.jobs.schemas import JobResponse


class MatchedSkillDetail(BaseModel):
    skill: str
    found_in_resume: bool
    required: bool


class JobMatchResult(BaseModel):
    job: JobResponse
    match_score: float
    hard_filter_passed: bool
    semantic_similarity: float | None = None
    skill_match_percentage: float | None = None
    matched_skills: list[MatchedSkillDetail] = []
    reasoning: str


class CompanyMatchGroup(BaseModel):
    company_name: str
    jobs: list[JobMatchResult]


class MatchesResponse(BaseModel):
    resume_id: uuid.UUID
    total_matches: int
    companies: list[CompanyMatchGroup] = []
    matches: list[JobMatchResult] = []


class EligibleJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    title: str
    company: str
    description: str | None = None
    location: str | None = None
    required_experience_years: int
    technical_skills: list[str] | None = None
    job_url: str | None = None
    source: str | None = None
    match_score: float
    reasoning: str
    semantic_similarity: float = 0.0
    skill_match_percentage: float = 0.0
    matched_skills: list[MatchedSkillDetail] = []
    work_model: str | None = None
    industry: str | None = None
    job_type: str | None = None


class EligibleJobsResponse(BaseModel):
    resume_id: uuid.UUID
    candidate_experience_years: int
    total_eligible: int
    eligible_jobs: list[EligibleJobSummary]
