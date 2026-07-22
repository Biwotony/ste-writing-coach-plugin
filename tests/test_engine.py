from app.engine import analyze, extract_literals
from app.models import AnalyzeRequest, DocumentType, Profile, TerminologyEntry


def issue_codes(response):
    return {
        issue.code
        for sentence in response.sentences
        for issue in sentence.issues
    } | {issue.code for issue in response.document_issues}


def test_detects_long_multi_action_procedure():
    response = analyze(
        AnalyzeRequest(
            text=(
                "Before you start the detailed inspection of the electrical equipment, "
                "disconnect the power supply and then remove the access panel from UNIT-42."
            ),
            profile=Profile.strict_ste,
            document_type=DocumentType.procedure,
        )
    )
    assert "SENT-001" in issue_codes(response)
    assert "PROC-002" in issue_codes(response)


def test_detects_passive_voice():
    response = analyze(
        AnalyzeRequest(
            text="The access panel is removed by the technician.",
            document_type=DocumentType.description,
        )
    )
    assert "VOICE-001" in issue_codes(response)


def test_uses_organization_terminology():
    response = analyze(
        AnalyzeRequest(
            text="Inspect the safety pressure valve.",
            terminology=[
                TerminologyEntry(
                    preferred="pressure-relief valve",
                    forbidden_synonyms=["safety pressure valve"],
                )
            ],
        )
    )
    assert "TERM-001" in issue_codes(response)
    assert response.sentences[0].rewrite_candidates


def test_warning_requires_label():
    response = analyze(
        AnalyzeRequest(
            text="Hot surfaces can cause burns. Wear gloves.",
            document_type=DocumentType.warning,
        )
    )
    assert "SAFE-001" in issue_codes(response)


def test_extracts_protected_literals():
    literals = extract_literals("Apply 28 V to UNIT-42 at 120.5 kPa. Check ECU-A1.")
    assert "28 V" in literals
    assert "UNIT-42" in literals
    assert "120.5 kPa" in literals
    assert "ECU-A1" in literals
