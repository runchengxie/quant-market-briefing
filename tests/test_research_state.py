import copy

import pytest

from market_briefing.research_state import (
    build_continuity,
    condition_id,
    prepare_state,
    validate_state,
)


@pytest.fixture
def state(analysis):
    def view(horizon):
        return {
            "horizon": horizon,
            "assessment_status": "available",
            "direction": "neutral",
            "confidence": "low",
            "path": "材料有限，判断震荡。",
            "claim_ids": ["c1"],
            "counterevidence": ["缺少更多观察"],
            "gap": "",
            "conditions": [],
        }

    return {
        "schema_version": "market.research-state.v1",
        "short_term": view("1-4w"),
        "long_term": view("6-12m"),
        "prior_conditions": [],
    }


def test_insufficient_is_not_neutral(state, analysis, evidence):
    state["short_term"].update(assessment_status="insufficient", gap="缺少历史观察")
    with pytest.raises(ValueError):
        validate_state(state, analysis, evidence, {"status": "absent"})
    state["short_term"].update(direction=None, confidence=None)
    validate_state(state, analysis, evidence, {"status": "absent"})


def test_available_long_term_matches_thesis(state, analysis, evidence):
    state["long_term"]["direction"] = "constructive"
    with pytest.raises(ValueError):
        validate_state(state, analysis, evidence, {"status": "absent"})


def test_legacy_prior_has_no_inferred_short_term(state, analysis):
    prior = {
        "status": "available",
        "identity": {"run_id": "old"},
        "documents": {"analysis": analysis},
    }
    result = build_continuity(prior, state)
    assert result["short_term"]["change"] == "unavailable"
    assert result["long_term"]["change"] == "unchanged"


def test_conditions_require_coverage_and_explicit_identity(state, analysis, evidence):
    old = copy.deepcopy(state)
    key = condition_id("old", "盈利预期下修")
    old["short_term"]["conditions"] = [{"id": key, "text": "盈利预期下修", "origin": "old"}]
    prior = {
        "status": "available",
        "identity": {"run_id": "old"},
        "documents": {"research-state": old},
    }
    with pytest.raises(ValueError):
        validate_state(state, analysis, evidence, prior)
    state["prior_conditions"] = [
        {
            "id": key,
            "status": "unresolved",
            "evidence_ids": [],
            "window": None,
            "explanation": "缺少覆盖",
        }
    ]
    validate_state(state, analysis, evidence, prior)
    state["prior_conditions"][0]["status"] = "not_observed"
    with pytest.raises(ValueError):
        validate_state(state, analysis, evidence, prior)


def test_projection_retains_analysis_conditions(state, analysis, evidence):
    prepared = prepare_state(state, analysis, evidence, {"status": "absent"})
    assert {c["text"] for c in prepared["long_term"]["conditions"]} >= set(
        analysis["invalidation_conditions"]
    )


def test_observed_condition_cannot_cite_estimate(state, analysis, evidence):
    key = condition_id("old", "盈利已实现下修")
    prior = {"status": "available", "documents": {"research-state": copy.deepcopy(state)}}
    prior["documents"]["research-state"]["short_term"]["conditions"] = [
        {"id": key, "origin": "old", "text": "盈利已实现下修"}
    ]
    state["prior_conditions"] = [
        {
            "id": key,
            "status": "observed",
            "evidence_ids": ["e2"],
            "window": None,
            "explanation": "未来盈利预测",
        }
    ]
    with pytest.raises(ValueError):
        validate_state(state, analysis, evidence, prior)


def test_prepare_does_not_overwrite_changed_prior_text(state, analysis, evidence):
    key = condition_id("old", "旧条件")
    prior = {"status": "available", "documents": {"research-state": copy.deepcopy(state)}}
    prior["documents"]["research-state"]["short_term"]["conditions"] = [
        {"id": key, "origin": "old", "text": "旧条件"}
    ]
    state["prior_conditions"] = [
        {
            "id": key,
            "status": "unresolved",
            "evidence_ids": [],
            "window": None,
            "explanation": "缺资料",
            "text": "篡改条件",
            "origin": "old",
        }
    ]
    with pytest.raises(ValueError):
        prepare_state(state, analysis, evidence, prior)


def test_supported_two_date_change(state):
    old = copy.deepcopy(state)
    state["short_term"].update(direction="constructive", confidence="medium")
    result = build_continuity({"status": "available", "documents": {"research-state": old}}, state)
    assert result["short_term"]["direction_changed"]
    assert result["short_term"]["confidence_changed"]


def test_negative_condition_requires_interval_coverage(state, analysis, evidence):
    key = condition_id("old", "旧条件")
    prior = {"status": "available", "documents": {"research-state": copy.deepcopy(state)}}
    prior["documents"]["research-state"]["short_term"]["conditions"] = [
        {"id": key, "origin": "old", "text": "旧条件"}
    ]
    state["prior_conditions"] = [
        {
            "id": key,
            "status": "not_observed",
            "evidence_ids": ["e1"],
            "window": {"start": "2026-10-02T21:00:00Z", "end": "2026-10-02T22:00:00Z"},
            "explanation": "仅有较早时点数据",
        }
    ]
    with pytest.raises(ValueError, match="coverage"):
        validate_state(state, analysis, evidence, prior)
