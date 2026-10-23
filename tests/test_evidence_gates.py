import copy

import pytest

from market_briefing.evidence_gates import (
    apply_findings,
    freeze_requirements,
    validate_attempt,
    validate_questions,
)


@pytest.fixture
def questions():
    def item(key, horizons):
        return {
            "id": key,
            "relevance": "可能改变判断",
            "horizons": horizons,
            "requirements": {
                "kind": "observation",
                "classification": "actual",
                "minimum": 1,
                "complete": False,
                "series_ids": [],
                "reference_periods": [],
            },
            "evidence_ids": ["e1"],
            "comparison_ids": [],
            "gap": "",
        }

    return {
        "schema_version": "market.research-questions.v1",
        "items": [item("q1", ["short_term"]), item("q2", ["long_term"])],
    }


def test_missing_only_blocks_dependent_horizon(questions, evidence, research_state):
    questions["items"][0]["evidence_ids"] = []
    findings = validate_questions(questions, evidence, {"results": [], "endpoints": []})
    state = apply_findings(research_state, findings)
    assert state["short_term"]["assessment_status"] == "insufficient"
    assert state["long_term"] == research_state["long_term"]


def test_repair_cannot_weaken_requirements(questions, evidence):
    frozen = freeze_requirements(questions)
    candidate = copy.deepcopy(questions)
    candidate["items"][0]["requirements"]["minimum"] = 0
    with pytest.raises(ValueError):
        validate_attempt(frozen, candidate, evidence, {"results": [], "endpoints": []})


def test_comparison_requires_result_and_both_endpoints(questions, evidence):
    questions["items"][0]["requirements"]["kind"] = "comparison"
    findings = validate_questions(questions, evidence, {"results": [], "endpoints": []})
    assert not findings["items"][0]["passed"]


def test_unknown_coverage_cannot_pass_complete_gate(questions, evidence):
    questions["items"][0]["requirements"]["complete"] = True
    assert not validate_questions(questions, evidence, {"results": [], "endpoints": []})["items"][
        0
    ]["passed"]


def test_classification_is_checked(questions, evidence):
    questions["items"][0]["evidence_ids"] = ["e2"]
    assert not validate_questions(questions, evidence, {"results": [], "endpoints": []})["items"][
        0
    ]["passed"]
