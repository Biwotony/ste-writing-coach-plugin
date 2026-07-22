from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .models import (
    AnalysisSummary,
    AnalyzeRequest,
    AnalyzeResponse,
    DocumentType,
    Issue,
    Profile,
    SentenceResult,
    Severity,
    TerminologyEntry,
)

DATA_DIR = Path(__file__).parent / "data"
STYLE_LEXICON: dict[str, str] = json.loads((DATA_DIR / "style_lexicon.json").read_text())

DISCLAIMER = (
    "This tool is an independent writing aid. It does not certify ASD-STE100 compliance, "
    "and it does not contain the official ASD-STE100 dictionary. A qualified human must "
    "verify technical meaning, safety information, terminology, and final compliance."
)

TOKEN_RE = re.compile(r"\b[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])|\n+(?=\S)")
LITERAL_RE = re.compile(
    r"\b(?:[A-Z]{2,}(?:-[A-Z0-9]+)*|\d+(?:\.\d+)?(?:\s?(?:V|A|Hz|kPa|MPa|mm|cm|m|kg|°C))?|[A-Z]+-\d+[A-Z0-9-]*)\b"
)

PASSIVE_AUX = r"(?:is|are|was|were|be|been|being|gets?|got)"
PAST_PARTICIPLE = r"(?:[A-Za-z]+ed|[A-Za-z]+en|built|made|done|given|shown|taken|set|put|found|kept|left|sent|read|written|installed|removed|connected|disconnected)"
PASSIVE_RE = re.compile(rf"\b{PASSIVE_AUX}\s+(?:\w+ly\s+)?{PAST_PARTICIPLE}\b", re.IGNORECASE)
ING_RE = re.compile(r"\b[A-Za-z]{3,}ing\b", re.IGNORECASE)
CONTRACTION_RE = re.compile(r"\b(?:can't|won't|don't|doesn't|isn't|aren't|it's|they're|you're|we're|shouldn't|couldn't|wouldn't)\b", re.IGNORECASE)
AMBIGUOUS_PRONOUN_RE = re.compile(r"\b(?:it|this|that|these|those|they|them)\b", re.IGNORECASE)
MODAL_RE = re.compile(r"\b(?:should|could|would|might|may)\b", re.IGNORECASE)
VAGUE_RE = re.compile(r"\b(?:appropriate|adequate|normally|generally|usually|as necessary|as required|carefully|properly)\b", re.IGNORECASE)
CONNECTOR_RE = re.compile(r"\b(?:and then|then|and)\b", re.IGNORECASE)
IMPERATIVE_VERBS = (
    r"(?:install|remove|connect|disconnect|open|close|turn|push|pull|set|make|check|"
    r"inspect|clean|apply|start|stop|wait|use|put|keep|measure|record|replace|"
    r"adjust|tighten|loosen|attach|detach|select|enter|verify)"
)
IMPERATIVE_START = re.compile(rf"^(?:do not\s+)?{IMPERATIVE_VERBS}\b", re.IGNORECASE)
IMPERATIVE_ANY = re.compile(rf"\b(?:do not\s+)?{IMPERATIVE_VERBS}\b", re.IGNORECASE)
IMPERATIVE_AFTER_CONNECTOR = re.compile(
    rf"\b(?:and then|then|and)\s+{IMPERATIVE_VERBS}\b",
    re.IGNORECASE,
)


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def split_sentences(text: str) -> list[str]:
    raw = [s.strip() for s in SENTENCE_RE.split(text.strip()) if s.strip()]
    result: list[str] = []
    for item in raw:
        # Preserve short labels such as WARNING: as part of the next content when possible.
        if result and len(TOKEN_RE.findall(item)) == 0:
            result[-1] += " " + item
        else:
            result.append(item)
    return result


def word_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def max_sentence_words(document_type: DocumentType, profile: Profile) -> int:
    if profile == Profile.ste_inspired:
        return 25
    if document_type in {DocumentType.procedure, DocumentType.warning}:
        return 20
    return 25


def _issue(
    *,
    code: str,
    severity: Severity,
    sentence_index: int | None,
    paragraph_index: int | None,
    message: str,
    explanation: str,
    sentence: str | None,
    matched_text: str | None,
    suggestion: str | None,
    rule_reference: str,
    review: bool = False,
) -> Issue:
    return Issue(
        code=code,
        severity=severity,
        sentence_index=sentence_index,
        paragraph_index=paragraph_index,
        message=message,
        explanation=explanation,
        sentence=sentence,
        matched_text=matched_text,
        suggestion=suggestion,
        rule_reference=rule_reference,
        requires_human_review=review,
    )


def terminology_map(entries: list[TerminologyEntry]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in entries:
        for synonym in entry.forbidden_synonyms:
            if synonym.strip():
                mapping[synonym.lower()] = entry.preferred
    return mapping


def lexical_replacements(sentence: str, terminology: list[TerminologyEntry]) -> list[Issue]:
    issues: list[Issue] = []
    combined = {**STYLE_LEXICON, **terminology_map(terminology)}
    lowered = sentence.lower()
    for source, target in sorted(combined.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
        match = pattern.search(sentence)
        if match:
            category = "TERM-001" if source in terminology_map(terminology) else "LEX-001"
            reference = (
                "Organization terminology profile"
                if category == "TERM-001"
                else "Configured controlled-language lexicon (not the official STE dictionary)"
            )
            issues.append(
                _issue(
                    code=category,
                    severity=Severity.warning,
                    sentence_index=None,
                    paragraph_index=None,
                    message=f"Use the preferred term '{target}'.",
                    explanation=(
                        "Use one term for one concept. The configured profile marks this expression "
                        "as non-preferred."
                    ),
                    sentence=sentence,
                    matched_text=match.group(0),
                    suggestion=pattern.sub(target, sentence, count=1),
                    rule_reference=reference,
                )
            )
            lowered = lowered.replace(source, target.lower())
    return issues


def make_rewrite_candidates(sentence: str, issues: list[Issue]) -> list[str]:
    candidates: list[str] = []
    current = sentence
    for source, target in sorted(STYLE_LEXICON.items(), key=lambda x: len(x[0]), reverse=True):
        current = re.sub(rf"\b{re.escape(source)}\b", target, current, flags=re.IGNORECASE)
    if current != sentence:
        candidates.append(current)

    if ";" in current:
        parts = [p.strip() for p in current.split(";") if p.strip()]
        if len(parts) > 1:
            candidate = ". ".join(p[:1].upper() + p[1:] for p in parts)
            if not candidate.endswith(('.', '!', '?')):
                candidate += "."
            candidates.append(candidate)

    if re.search(r"\band then\b", current, re.IGNORECASE):
        parts = re.split(r"\band then\b", current, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and all(p.strip() for p in parts):
            left = parts[0].strip().rstrip(".,;") + "."
            right = parts[1].strip()
            right = right[:1].upper() + right[1:]
            if not right.endswith(('.', '!', '?')):
                right += "."
            candidates.append(f"{left} {right}")

    for issue in issues:
        if issue.suggestion and issue.suggestion not in candidates:
            candidates.append(issue.suggestion)
    return candidates[:3]


def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    paragraphs = split_paragraphs(request.text)
    sentences = split_sentences(request.text)
    results: list[SentenceResult] = []
    all_sentence_issues: list[Issue] = []
    limit = max_sentence_words(request.document_type, request.profile)

    # Map sentence text to paragraph index. This is intentionally conservative.
    paragraph_positions: list[tuple[int, int, str]] = []
    cursor = 0
    for p_index, paragraph in enumerate(paragraphs):
        start = request.text.find(paragraph, cursor)
        paragraph_positions.append((start, start + len(paragraph), paragraph))
        cursor = start + len(paragraph)

    search_cursor = 0
    for s_index, sentence in enumerate(sentences):
        s_pos = request.text.find(sentence, search_cursor)
        search_cursor = max(search_cursor, s_pos + len(sentence))
        paragraph_index = 0
        for p_index, (p_start, p_end, _) in enumerate(paragraph_positions):
            if p_start <= s_pos <= p_end:
                paragraph_index = p_index
                break

        issues: list[Issue] = []
        wc = word_count(sentence)
        if wc > limit:
            issues.append(
                _issue(
                    code="SENT-001",
                    severity=Severity.error if request.profile == Profile.strict_ste else Severity.warning,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message=f"The sentence has {wc} words. The configured limit is {limit}.",
                    explanation="Short sentences reduce ambiguity and make instructions easier to translate.",
                    sentence=sentence,
                    matched_text=None,
                    suggestion="Split the sentence into two or more sentences.",
                    rule_reference="Configured sentence-length rule",
                    review=True,
                )
            )

        passive = PASSIVE_RE.search(sentence)
        if passive:
            issues.append(
                _issue(
                    code="VOICE-001",
                    severity=Severity.warning,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message="Possible passive voice.",
                    explanation="Name the person or component that does the action when this is technically correct.",
                    sentence=sentence,
                    matched_text=passive.group(0),
                    suggestion="Rewrite the sentence in the active voice.",
                    rule_reference="Configured active-voice rule",
                    review=True,
                )
            )

        ing = ING_RE.search(sentence)
        if ing and request.profile == Profile.strict_ste:
            issues.append(
                _issue(
                    code="VERB-ING-001",
                    severity=Severity.review,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message="Review the '-ing' word.",
                    explanation=(
                        "An '-ing' form can have several grammatical functions. Confirm that the "
                        "configured STE profile permits this use."
                    ),
                    sentence=sentence,
                    matched_text=ing.group(0),
                    suggestion="Use a finite verb or a clearer noun when possible.",
                    rule_reference="Configured verb-form review rule",
                    review=True,
                )
            )

        contraction = CONTRACTION_RE.search(sentence)
        if contraction:
            expansion = {
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
            }[contraction.group(0).lower()]
            suggestion = sentence[: contraction.start()] + expansion + sentence[contraction.end() :]
            issues.append(
                _issue(
                    code="GRAM-001",
                    severity=Severity.warning,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message="Do not use a contraction in controlled technical text.",
                    explanation="The full form is easier to identify and translate consistently.",
                    sentence=sentence,
                    matched_text=contraction.group(0),
                    suggestion=suggestion,
                    rule_reference="Configured grammar rule",
                )
            )

        modal = MODAL_RE.search(sentence)
        if modal and request.document_type == DocumentType.procedure:
            issues.append(
                _issue(
                    code="PROC-001",
                    severity=Severity.review,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message="Review the modal verb in this procedural sentence.",
                    explanation="A direct command is usually clearer than a recommendation or possibility.",
                    sentence=sentence,
                    matched_text=modal.group(0),
                    suggestion="Use a direct imperative when the action is mandatory.",
                    rule_reference="Configured procedure rule",
                    review=True,
                )
            )

        if request.document_type == DocumentType.procedure:
            second_action = IMPERATIVE_AFTER_CONNECTOR.search(sentence)
            first_action = (
                IMPERATIVE_ANY.search(sentence[: second_action.start()])
                if second_action
                else None
            )
            if second_action and first_action:
                issues.append(
                    _issue(
                        code="PROC-002",
                        severity=Severity.error,
                        sentence_index=s_index,
                        paragraph_index=paragraph_index,
                        message="This sentence can contain more than one instruction.",
                        explanation="Put each action in a separate sentence or numbered step.",
                        sentence=sentence,
                        matched_text=second_action.group(0),
                        suggestion="Split the actions into separate instructions.",
                        rule_reference="Configured one-instruction-per-sentence rule",
                        review=True,
                    )
                )

        vague = VAGUE_RE.search(sentence)
        if vague:
            issues.append(
                _issue(
                    code="CLARITY-001",
                    severity=Severity.review,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message="This expression can be vague.",
                    explanation="Replace subjective wording with a measurable condition or explicit criterion.",
                    sentence=sentence,
                    matched_text=vague.group(0),
                    suggestion="Add a measurable limit, condition, or result.",
                    rule_reference="Configured clarity rule",
                    review=True,
                )
            )

        # Pronoun ambiguity is only flagged when the sentence contains multiple noun-like tokens.
        pronoun = AMBIGUOUS_PRONOUN_RE.search(sentence)
        capital_or_long_nouns = re.findall(r"\b(?:[A-Z][A-Za-z0-9-]+|[A-Za-z]{7,})\b", sentence)
        if pronoun and len(capital_or_long_nouns) >= 2:
            issues.append(
                _issue(
                    code="REF-001",
                    severity=Severity.review,
                    sentence_index=s_index,
                    paragraph_index=paragraph_index,
                    message="The pronoun can have an unclear reference.",
                    explanation="Repeat the specific noun when more than one reference is possible.",
                    sentence=sentence,
                    matched_text=pronoun.group(0),
                    suggestion="Replace the pronoun with the applicable component or person.",
                    rule_reference="Configured reference-clarity rule",
                    review=True,
                )
            )

        lex_issues = lexical_replacements(sentence, request.terminology)
        for item in lex_issues:
            item.sentence_index = s_index
            item.paragraph_index = paragraph_index
        issues.extend(lex_issues)

        candidates = make_rewrite_candidates(sentence, issues) if request.include_rewrite_candidates else []
        result = SentenceResult(
            index=s_index,
            text=sentence,
            word_count=wc,
            issues=issues,
            rewrite_candidates=candidates,
        )
        results.append(result)
        all_sentence_issues.extend(issues)

    document_issues: list[Issue] = []
    for p_index, paragraph in enumerate(paragraphs):
        p_sentences = split_sentences(paragraph)
        if len(p_sentences) > 6:
            document_issues.append(
                _issue(
                    code="PARA-001",
                    severity=Severity.warning,
                    sentence_index=None,
                    paragraph_index=p_index,
                    message=f"Paragraph {p_index + 1} has {len(p_sentences)} sentences.",
                    explanation="A short paragraph should develop one topic.",
                    sentence=None,
                    matched_text=None,
                    suggestion="Split the paragraph by topic.",
                    rule_reference="Configured paragraph-length rule",
                    review=True,
                )
            )

    if request.document_type == DocumentType.warning:
        first = request.text.lstrip().upper()
        if not (first.startswith("WARNING") or first.startswith("CAUTION")):
            document_issues.append(
                _issue(
                    code="SAFE-001",
                    severity=Severity.error,
                    sentence_index=None,
                    paragraph_index=0,
                    message="The safety text does not start with WARNING or CAUTION.",
                    explanation="Use an explicit safety label according to the organization's approved format.",
                    sentence=None,
                    matched_text=None,
                    suggestion="Add the approved safety label and verify the hazard statement.",
                    rule_reference="Organization safety-writing profile",
                    review=True,
                )
            )

    all_issues = all_sentence_issues + document_issues
    counts = Counter(issue.severity.value for issue in all_issues)
    review_count = sum(1 for issue in all_issues if issue.requires_human_review)
    penalty = (
        counts[Severity.error.value] * 10
        + counts[Severity.warning.value] * 5
        + counts[Severity.review.value] * 3
        + counts[Severity.info.value]
    )
    readiness_score = max(0, 100 - penalty)
    if readiness_score >= 90 and not counts[Severity.error.value]:
        status = "ready_for_human_review"
    elif readiness_score >= 70:
        status = "revision_recommended"
    else:
        status = "significant_revision_required"

    summary = AnalysisSummary(
        sentence_count=len(sentences),
        paragraph_count=len(paragraphs),
        word_count=word_count(request.text),
        issue_count=len(all_issues),
        by_severity={severity.value: counts[severity.value] for severity in Severity},
        readiness_score=readiness_score,
        status=status,
        unresolved_human_review_items=review_count,
    )
    return AnalyzeResponse(
        profile=request.profile,
        document_type=request.document_type,
        disclaimer=DISCLAIMER,
        summary=summary,
        sentences=results,
        document_issues=document_issues,
    )


def extract_literals(text: str) -> list[str]:
    return sorted(set(match.group(0) for match in LITERAL_RE.finditer(text)))
