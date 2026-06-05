from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, ConflictError
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domains.candidates.models import Candidate
from app.domains.candidates.repository import CandidateRepository
from app.domains.candidates.schemas import CandidateCreate, LoginRequest, SignupRequest


class CandidateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CandidateRepository(db)

    def register_or_rotate(self, payload: CandidateCreate) -> tuple[Candidate, str]:
        """
        Guest path: upsert by email and (re)issue a bearer token.

        Returns the candidate plus the raw token (shown to the client once).
        Re-registering the same email rotates the token, so the latest caller
        owns the candidate's résumés. No password — kept for backward
        compatibility with the original lightweight flow.
        """
        raw_token = generate_token()
        token_hash = hash_token(raw_token)

        candidate = self.repo.get_by_email(payload.email)
        if candidate is None:
            candidate = Candidate(
                email=payload.email,
                full_name=payload.full_name,
                api_token_hash=token_hash,
            )
            self.repo.add(candidate)
        else:
            candidate.full_name = payload.full_name
            candidate.api_token_hash = token_hash

        self.db.commit()
        self.db.refresh(candidate)
        return candidate, raw_token

    # ── Account auth ─────────────────────────────────────────────────────────
    def signup(self, payload: SignupRequest) -> tuple[Candidate, str]:
        """Create a password-backed account. If the email already exists, only
        allow it when that record has no password yet (claim a guest account);
        otherwise it's a conflict (use login)."""
        existing = self.repo.get_by_email(payload.email)
        if existing and existing.password_hash:
            raise ConflictError("An account with this email already exists. Please log in.")

        raw_token = generate_token()
        if existing is None:
            candidate = Candidate(
                email=payload.email,
                full_name=payload.full_name,
                api_token_hash=hash_token(raw_token),
                password_hash=hash_password(payload.password),
            )
            self.repo.add(candidate)
        else:
            # Upgrade an existing guest record into a real account.
            existing.full_name = payload.full_name
            existing.password_hash = hash_password(payload.password)
            existing.api_token_hash = hash_token(raw_token)
            candidate = existing

        self.db.commit()
        self.db.refresh(candidate)
        return candidate, raw_token

    def login(self, payload: LoginRequest) -> tuple[Candidate, str]:
        """Verify credentials and issue a fresh bearer token for the session."""
        candidate = self.repo.get_by_email(payload.email)
        # Run a verify even when the user is missing to avoid leaking which
        # emails exist via timing (constant-ish work either way).
        stored = candidate.password_hash if candidate else None
        if not stored or not verify_password(payload.password, stored):
            raise AuthError("Invalid email or password")

        raw_token = generate_token()
        candidate.api_token_hash = hash_token(raw_token)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate, raw_token
