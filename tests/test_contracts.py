import pytest

from market_briefing.contracts import validate_document


def test_valid_evidence(evidence):
    validate_document(evidence, "evidence")


@pytest.mark.parametrize(
    "case",
    ["extra", "timestamp", "unit", "duplicate", "source", "period", "future", "date", "nonfinite"],
)
def test_reject_invalid_evidence(evidence, case):
    if case == "extra":
        evidence["surprise"] = 1
    elif case == "timestamp":
        evidence["collected_at"] = "2026-10-02T22:00:00"
    elif case == "unit":
        evidence["observations"][0]["unit"] = "unknown_unit"
    elif case == "duplicate":
        evidence["observations"][1]["id"] = evidence["observations"][0]["id"]
    elif case == "source":
        evidence["observations"][0]["source_id"] = "unknown"
    elif case == "period":
        evidence["observations"][0]["reference_period"] = ""
    elif case == "future":
        evidence["sources"][0]["published_at"] = "2026-10-03T12:00:00Z"
    elif case == "date":
        evidence["market_date"] = "2026-02-30"
    else:
        evidence["observations"][0]["value"] = float("nan")
    with pytest.raises(ValueError):
        validate_document(evidence, "evidence")


def test_analysis_rejects_dangling_claim(analysis):
    analysis["sections"][0]["claim_ids"] = ["absent"]
    with pytest.raises(ValueError):
        validate_document(analysis, "analysis")


def test_verified_text_event_is_supported(evidence):
    event = dict(
        evidence["observations"][0],
        id="event",
        metric="company_announcement",
        unit="text",
        value="公司预计下一季度增加资本投入。",
    )
    evidence["observations"].append(event)
    validate_document(evidence, "evidence")


def test_numeric_metric_cannot_use_text_unit(evidence):
    evidence["observations"][0]["unit"] = "text"
    with pytest.raises(ValueError):
        validate_document(evidence, "evidence")
