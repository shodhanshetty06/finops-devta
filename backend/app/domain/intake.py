"""Domain schemas for Phase 4 input ingestion (Excel questionnaire upload and
natural-language requirement extraction)."""
from pydantic import BaseModel

from app.domain.assumption import Assumption
from app.domain.enums import Severity
from app.domain.estimate import EstimateResult
from app.domain.requirements import CustomerRequirement


class ParseIssue(BaseModel):
    field: str
    message: str
    severity: Severity


class IntakeResponse(BaseModel):
    """Shared response shape for both the Excel and natural-language intake
    endpoints. `requirement` is None only when nothing usable could be
    extracted at all (e.g. an unreadable file, or free text with no
    signal) - the caller should always check `issues` for BLOCKER entries
    even when `requirement` is present, since some fields may have been
    skipped."""

    requirement: CustomerRequirement | None
    issues: list[ParseIssue] = []
    notes: list[Assumption] = []
    estimate: EstimateResult | None = None
    # "template" - matched the platform's own questionnaire layout, no LLM
    # call made. "ai" - an arbitrary customer layout was understood via
    # Groq extraction (see app/services/extraction_service.py); every
    # extracted value is still validated by the same schema/coercion rules
    # as the template path, and every substitution appears in `notes`.
    # "unrecognized" - neither path could confidently identify any
    # requirement; `requirement` is None and `issues` explains why.
    extraction_source: str = "template"


class TextIntakeRequest(BaseModel):
    project_name: str
    text: str
    region_hint: str | None = None
