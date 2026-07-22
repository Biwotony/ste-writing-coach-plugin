from __future__ import annotations

import re

from .engine import DISCLAIMER, STYLE_LEXICON, analyze, extract_literals, terminology_map
from .models import (
    AnalyzeRequest,
    AppliedChange,
    RewriteRequest,
    RewriteResponse,
    RewriteStrategy,
)

CONTRACTIONS: dict[str, str] = {
    "can't": "cannot",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "isn't": "is not",
    "aren't": "are not",
    "it's": "it is",
    "they're": "they are",
    "you're": "you are",
    "we're": "we are",
    "shouldn't": "should not",
    "couldn't": "could not",
    "wouldn't": "would not",
}

SPLIT_CONNECTOR_RE = re.compile(
    r"\b(?:and then|then)\s+(?=(?:install|remove|connect|disconnect|open|close|turn|push|pull|set|make|check|inspect|clean|apply|start|stop|wait|use|put|keep|measure|record|replace|adjust|tighten|loosen|attach|detach|select|enter|verify)\b)",
    re.IGNORECASE,
)


def _replace_case_insensitive(
    text: str,
    source: str,
    replacement: str,
    reason: str,
    changes: list[AppliedChange],
) -> str:
    pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
    if not pattern.search(text):
        return text

    def repl(match: re.Match[str]) -> str:
        value = replacement
        if match.group(0)[:1].isupper():
            value = value[:1].upper() + value[1:]
        return value

    updated, count = pattern.subn(repl, text)
    if count:
        changes.append(AppliedChange(source=source, replacement=replacement, reason=reason))
    return updated


def _split_steps(text: str, changes: list[AppliedChange]) -> str:
    parts = SPLIT_CONNECTOR_RE.split(text, maxsplit=1)
    if len(parts) != 2:
        return text
    left = parts[0].strip().rstrip(".,;:")
    right = parts[1].strip()
    if not left or not right:
        return text
    left += "."
    right = right[:1].upper() + right[1:]
    if right[-1:] not in ".!?”\"'":
        right += "."
    changes.append(
        AppliedChange(
            source="and then/then",
            replacement="sentence break",
            reason="Put procedural actions in separate instructions.",
        )
    )
    return f"{left} {right}"


def rewrite(request: RewriteRequest) -> RewriteResponse:
    revised = request.text
    changes: list[AppliedChange] = []

    # Organization terminology has priority over the sample style lexicon.
    replacements = {**STYLE_LEXICON, **terminology_map(request.terminology)}
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        revised = _replace_case_insensitive(
            revised,
            source,
            target,
            "Use the configured preferred wording.",
            changes,
        )

    for source, target in CONTRACTIONS.items():
        revised = _replace_case_insensitive(
            revised,
            source,
            target,
            "Do not use contractions in controlled technical text.",
            changes,
        )

    if request.strategy in {RewriteStrategy.direct, RewriteStrategy.stepwise}:
        revised = _split_steps(revised, changes)

    if request.strategy == RewriteStrategy.stepwise and ";" in revised:
        segments = [segment.strip() for segment in revised.split(";") if segment.strip()]
        if len(segments) > 1:
            revised = ". ".join(segment[:1].upper() + segment[1:] for segment in segments)
            if revised[-1:] not in ".!?":
                revised += "."
            changes.append(
                AppliedChange(
                    source="semicolon",
                    replacement="sentence break",
                    reason="Separate actions or ideas for easier review.",
                )
            )

    analysis_request = AnalyzeRequest(
        text=revised,
        profile=request.profile,
        document_type=request.document_type,
        terminology=request.terminology,
        include_rewrite_candidates=False,
    )
    remaining = analyze(analysis_request)

    original_literals = extract_literals(request.text)
    revised_literals = extract_literals(revised)
    missing = sorted(set(original_literals) - set(revised_literals))
    added = sorted(set(revised_literals) - set(original_literals))
    warnings: list[str] = []
    if missing:
        warnings.append("The rewrite removed protected literals. Restore or verify them.")
    if added:
        warnings.append("The rewrite added protected literals. Verify them.")
    warnings.append("Verify technical meaning, safety information, and action sequence before use.")

    return RewriteResponse(
        original=request.text,
        revised=revised,
        strategy=request.strategy,
        applied_changes=changes,
        remaining_analysis=remaining,
        protected_literals={
            "original": original_literals,
            "revised": revised_literals,
            "missing_from_revised": missing,
            "new_in_revised": added,
        },
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
