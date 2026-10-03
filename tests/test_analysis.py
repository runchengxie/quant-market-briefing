import pytest

from market_briefing.analysis import validate_analysis


def test_analysis_links(analysis, evidence):
    validate_analysis(analysis, evidence)


@pytest.mark.parametrize("case", ["missing", "unverified", "null", "classification"])
def test_invalid_claim_links(analysis, evidence, case):
    if case == "missing":
        analysis["claims"][0]["evidence_ids"] = ["absent"]
    elif case == "unverified":
        evidence["observations"][0]["verification"] = "unverified"
    elif case == "null":
        evidence["observations"][0]["value"] = None
    else:
        analysis["claims"][1]["temporal_type"] = "actual"
    with pytest.raises(ValueError):
        validate_analysis(analysis, evidence)
