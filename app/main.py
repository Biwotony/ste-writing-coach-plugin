from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .engine import DISCLAIMER, analyze, extract_literals
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CompareRequest,
    CompareResponse,
    RewriteRequest,
    RewriteResponse,
)
from .rewrite import rewrite

app = FastAPI(
    title="STE Writing Coach API",
    version="0.1.0",
    description=(
        "Independent controlled-language checking API for a Custom GPT Action. "
        "It does not certify ASD-STE100 compliance."
    ),
    contact={"name": "STE Writing Coach administrator"},
    license_info={"name": "MIT"},
)

origins = [item.strip() for item in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def require_api_key(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("STE_API_KEY", "").strip()
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
        )


Auth = Annotated[None, Depends(require_api_key)]


@app.get("/health", operation_id="healthCheck", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ste-writing-coach", "version": "0.1.0"}


@app.get("/v1/rules", operation_id="listConfiguredRules", tags=["analysis"])
def list_rules(_: Auth) -> dict[str, object]:
    return {
        "disclaimer": DISCLAIMER,
        "rules": [
            {"code": "SENT-001", "name": "Configured sentence-length limit"},
            {"code": "VOICE-001", "name": "Possible passive voice"},
            {"code": "VERB-ING-001", "name": "Review -ing forms"},
            {"code": "GRAM-001", "name": "Avoid contractions"},
            {"code": "PROC-001", "name": "Review modal verbs in procedures"},
            {"code": "PROC-002", "name": "One instruction per sentence"},
            {"code": "CLARITY-001", "name": "Replace vague expressions"},
            {"code": "REF-001", "name": "Resolve unclear pronouns"},
            {"code": "LEX-001", "name": "Configured preferred wording"},
            {"code": "TERM-001", "name": "Organization terminology"},
            {"code": "PARA-001", "name": "Paragraph topic and length"},
            {"code": "SAFE-001", "name": "Safety-label review"},
        ],
    }


@app.post("/v1/analyze", response_model=AnalyzeResponse, operation_id="analyzeText", tags=["analysis"])
def analyze_text(request: AnalyzeRequest, _: Auth) -> AnalyzeResponse:
    return analyze(request)


@app.post("/v1/rewrite", response_model=RewriteResponse, operation_id="rewriteText", tags=["rewrite"])
def rewrite_text(request: RewriteRequest, _: Auth) -> RewriteResponse:
    return rewrite(request)


@app.post("/v1/compare", response_model=CompareResponse, operation_id="compareTexts", tags=["analysis"])
def compare_texts(request: CompareRequest, _: Auth) -> CompareResponse:
    base = dict(
        profile=request.profile,
        document_type=request.document_type,
        terminology=request.terminology,
        include_rewrite_candidates=False,
    )
    original_analysis = analyze(AnalyzeRequest(text=request.original, **base))
    revised_analysis = analyze(AnalyzeRequest(text=request.revised, **base))

    original_literals = extract_literals(request.original)
    revised_literals = extract_literals(request.revised)
    missing = sorted(set(original_literals) - set(revised_literals))
    added = sorted(set(revised_literals) - set(original_literals))
    warnings: list[str] = []
    if missing:
        warnings.append("The revised text does not contain all protected literals from the original.")
    if added:
        warnings.append("The revised text contains new literals. Verify that they are correct.")
    if not warnings:
        warnings.append("No obvious part-number, acronym, or numeric literal changes were detected.")

    return CompareResponse(
        original_analysis=original_analysis,
        revised_analysis=revised_analysis,
        score_change=(
            revised_analysis.summary.readiness_score
            - original_analysis.summary.readiness_score
        ),
        issue_change=(
            revised_analysis.summary.issue_count - original_analysis.summary.issue_count
        ),
        preserved_literals={
            "original": original_literals,
            "revised": revised_literals,
            "missing_from_revised": missing,
            "new_in_revised": added,
        },
        warnings=warnings,
    )
