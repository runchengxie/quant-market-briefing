import copy

import pytest

from market_briefing.structured import analyze_structured


def test_repair_is_bounded_and_preserves_failures(
    tmp_path, evidence, analysis, research_state, monkeypatch
):
    from market_briefing.prior import load_prior

    def q(key, h):
        return {
            "id": key,
            "relevance": "关键缺口",
            "horizons": [h],
            "requirements": {
                "kind": "comparison",
                "classification": "actual",
                "minimum": 2,
                "complete": True,
                "series_ids": [],
                "reference_periods": [],
            },
            "evidence_ids": [],
            "comparison_ids": [],
            "gap": "缺历史",
        }

    envelope = {
        "analysis": analysis,
        "state": research_state,
        "questions": {
            "schema_version": "market.research-questions.v1",
            "items": [q("q1", "short_term"), q("q2", "long_term")],
        },
    }
    calls = []

    def stage(*a, **kw):
        calls.append(kw)
        return copy.deepcopy(envelope)

    monkeypatch.setattr("market_briefing.structured.execute_stage", stage)
    a, members = analyze_structured(
        evidence, {"run_dir": tmp_path, "prior": load_prior(None, evidence["market_date"], None)}
    )
    assert len(calls) == 2
    assert members["research-state.json"]["short_term"]["assessment_status"] == "insufficient"
    assert members["research-attempt-0001.json"]["findings"]["blocked_horizons"]
    assert members["research-attempt-0002.json"]["findings"]["blocked_horizons"]
    assert a == analysis


def test_repair_may_not_change_criteria(tmp_path, evidence, analysis, research_state, monkeypatch):
    from market_briefing.prior import load_prior

    def q(key):
        return {
            "id": key,
            "relevance": "关键缺口",
            "horizons": ["short_term"],
            "requirements": {
                "kind": "observation",
                "classification": "actual",
                "minimum": 2,
                "complete": False,
                "series_ids": [],
                "reference_periods": [],
            },
            "evidence_ids": [],
            "comparison_ids": [],
            "gap": "缺少证据",
        }

    envelope = {
        "analysis": analysis,
        "state": research_state,
        "questions": {
            "schema_version": "market.research-questions.v1",
            "items": [q("q1"), q("q2")],
        },
    }
    count = 0

    def stage(*a, **kw):
        nonlocal count
        count += 1
        result = copy.deepcopy(envelope)
        if count == 2:
            result["questions"]["items"][0]["requirements"]["minimum"] = 1
        return result

    monkeypatch.setattr("market_briefing.structured.execute_stage", stage)
    with pytest.raises(ValueError, match="requirements"):
        analyze_structured(
            evidence,
            {"run_dir": tmp_path, "prior": load_prior(None, evidence["market_date"], None)},
        )
