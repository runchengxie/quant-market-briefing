import json
from datetime import UTC, datetime

import pytest


@pytest.mark.parametrize("value,verification", [(105, "unverified"), (None, "verified")])
def test_event_claim_cannot_launder_invalid_observation(
    weekly_evidence, weekly_analysis, value, verification
):
    from market_briefing.weekly.contracts import validate_weekly_analysis

    weekly_evidence["observations"][1].update(value=value, verification=verification)
    with pytest.raises(ValueError):
        validate_weekly_analysis(weekly_analysis, weekly_evidence)


@pytest.mark.parametrize(
    "mode", ["scheduled_as_realized", "estimate_as_realized", "realized_as_estimate"]
)
def test_claim_temporal_type_must_match_underlying_records(weekly_evidence, weekly_analysis, mode):
    from market_briefing.weekly.contracts import validate_weekly_analysis

    if mode == "scheduled_as_realized":
        weekly_analysis["claims"][1]["temporal_type"] = "realized"
    elif mode == "estimate_as_realized":
        weekly_evidence["observations"][1]["classification"] = "estimate"
    else:
        weekly_analysis["claims"][0]["temporal_type"] = "estimate"
    with pytest.raises(ValueError):
        validate_weekly_analysis(weekly_analysis, weekly_evidence)


@pytest.mark.parametrize("field", ["headline", "heading"])
def test_visible_titles_cannot_invent_numeric_claims(
    weekly_evidence, weekly_analysis, weekly_editor_output, field
):
    from market_briefing.weekly.editor import assemble_weekly_briefing

    if field == "headline":
        weekly_editor_output["headline"] = "股市上涨999%"
    else:
        weekly_editor_output["sections"][0]["heading"] = "股市上涨999%"
    brief = assemble_weekly_briefing(
        weekly_editor_output, weekly_evidence, weekly_analysis, "run", 1
    )
    assert brief["quality"]["errors"]


def test_readable_export_contains_week_cutoff_and_missing_inputs(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
):
    from .test_editor_cli import run_week

    _, run, _, _ = run_week(tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output)
    text = (run / "briefing.txt").read_text(encoding="utf-8")
    assert "2026-09-28" in text
    assert "2026-10-03" in text
    assert "缺少真实资料" in text


def test_weekly_comparison_cannot_use_unrelated_completed_endpoints(weekly_evidence):
    from market_briefing.weekly.comparisons import calculate_comparison
    from market_briefing.weekly.contracts import validate_weekly_document

    weekly_evidence["observations"][0].update(
        reference_period="2026-09-18", observed_at="2026-09-18T20:00:00Z"
    )
    start, end = weekly_evidence["observations"]
    weekly_evidence["comparisons"] = [calculate_comparison(start, end, "return")]
    with pytest.raises(ValueError):
        validate_weekly_document(weekly_evidence, "weekly-evidence")


def test_previous_week_context_rejects_mechanically_invalid_validated_label(
    tmp_path, weekly_evidence, weekly_analysis, weekly_briefing
):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.context import load_weekly_context

    weekly_briefing["sections"][0]["text"] = "上涨999%。"
    weekly_briefing["brief_text"] = "\n\n".join(
        f"{s['heading']}\n{s['text']}" for s in weekly_briefing["sections"]
    )
    for name, doc in [
        ("evidence", weekly_evidence),
        ("analysis", weekly_analysis),
        ("briefing", weekly_briefing),
    ]:
        (tmp_path / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    now = datetime(2026, 10, 10, 8, tzinfo=UTC)
    with pytest.raises(ValueError):
        load_weekly_context(None, tmp_path, select_week(now), now)


def test_challenge_corrected_endpoint_remaps_exact_comparison_id(weekly_evidence, weekly_analysis):
    import copy

    from market_briefing.weekly.research import assemble_weekly_research, reconcile_weekly_revision

    from .test_research import candidate

    initial = candidate(weekly_evidence, weekly_analysis)
    initial["analysis"]["comparison_ids"] = ["cmp_o1_o2_return"]
    initial["analysis"]["claims"][0]["evidence_ids"] = ["cmp_o1_o2_return"]
    revised = copy.deepcopy(initial)
    revised["observations"][0]["value"] = 101
    reconciled, mapping = reconcile_weekly_revision(initial, revised)
    expected = f"cmp_{mapping['observations']['o1']}_o2_return"
    assert reconciled["analysis"]["comparison_ids"] == [expected]
    assert reconciled["analysis"]["claims"][0]["evidence_ids"] == [expected]
    metadata = {
        key: value
        for key, value in weekly_evidence.items()
        if key
        not in [
            "sources",
            "observations",
            "events",
            "scheduled_events",
            "comparisons",
            "missing_inputs",
        ]
    }
    evidence, analysis = assemble_weekly_research(reconciled, metadata, {})
    assert evidence["comparisons"][0]["id"] == expected
