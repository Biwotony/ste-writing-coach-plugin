from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Profile(str, Enum):
    strict_ste = "strict_ste"
    ste_inspired = "ste_inspired"


class DocumentType(str, Enum):
    procedure = "procedure"
    description = "description"
    warning = "warning"
    general = "general"
    literary_summary = "literary_summary"


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    review = "review"
    info = "info"


class TerminologyCategory(str, Enum):
    technical_noun = "technical_noun"
    technical_verb = "technical_verb"
    general = "general"


class TerminologyEntry(BaseModel):
    preferred: str = Field(min_length=1, max_length=200)
    forbidden_synonyms: list[str] = Field(default_factory=list)
    definition: str | None = Field(default=None, max_length=1000)
    category: TerminologyCategory = TerminologyCategory.general

    @field_validator("preferred")
    @classmethod
    def normalize_preferred(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("preferred must not be empty")
        return value

    @field_validator("forbidden_synonyms")
    @classmethod
    def normalize_synonyms(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            value = value.strip()
            if value and value.casefold() not in seen:
                result.append(value)
                seen.add(value.casefold())
        return result


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    profile: Profile = Profile.strict_ste
    document_type: DocumentType = DocumentType.procedure
    terminology: list[TerminologyEntry] = Field(default_factory=list, max_length=500)
    include_rewrite_candidates: bool = True

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain visible characters")
        return value


class RewriteStrategy(str, Enum):
    minimal = "minimal"
    direct = "direct"
    stepwise = "stepwise"


class RewriteRequest(AnalyzeRequest):
    strategy: RewriteStrategy = RewriteStrategy.direct


class CompareRequest(BaseModel):
    original: str = Field(min_length=1, max_length=100_000)
    revised: str = Field(min_length=1, max_length=100_000)
    profile: Profile = Profile.strict_ste
    document_type: DocumentType = DocumentType.procedure
    terminology: list[TerminologyEntry] = Field(default_factory=list, max_length=500)


class Issue(BaseModel):
    code: str
    severity: Severity
    sentence_index: int | None = None
    paragraph_index: int | None = None
    message: str
    explanation: str
    sentence: str | None = None
    matched_text: str | None = None
    suggestion: str | None = None
    rule_reference: str
    requires_human_review: bool = False


class SentenceResult(BaseModel):
    index: int
    text: str
    word_count: int
    issues: list[Issue] = Field(default_factory=list)
    rewrite_candidates: list[str] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    sentence_count: int
    paragraph_count: int
    word_count: int
    issue_count: int
    by_severity: dict[str, int]
    readiness_score: int = Field(ge=0, le=100)
    status: str
    unresolved_human_review_items: int


class AnalyzeResponse(BaseModel):
    profile: Profile
    document_type: DocumentType
    disclaimer: str
    summary: AnalysisSummary
    sentences: list[SentenceResult]
    document_issues: list[Issue] = Field(default_factory=list)


class AppliedChange(BaseModel):
    source: str
    replacement: str
    reason: str


class RewriteResponse(BaseModel):
    original: str
    revised: str
    strategy: RewriteStrategy
    applied_changes: list[AppliedChange] = Field(default_factory=list)
    remaining_analysis: AnalyzeResponse
    protected_literals: dict[str, list[str]]
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str


class CompareResponse(BaseModel):
    original_analysis: AnalyzeResponse
    revised_analysis: AnalyzeResponse
    score_change: int
    issue_change: int
    preserved_literals: dict[str, list[str]]
    warnings: list[str]


class ErrorResponse(BaseModel):
    detail: str | list[dict[str, Any]]
