import copy

import pytest


def test_weekly_contract_and_future_schedule(weekly_evidence, weekly_analysis):
    from market_briefing.weekly.contracts import validate_weekly_analysis, validate_weekly_document

    validate_weekly_document(weekly_evidence, "weekly-evidence")
    validate_weekly_analysis(weekly_analysis, weekly_evidence)
    weekly_evidence["sources"][0]["published_at"] = None
    validate_weekly_document(weekly_evidence, "weekly-evidence")


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "source",
        "future_source",
        "future_known",
        "future_observation",
        "event_window",
        "collection",
        "week",
        "nonfinite",
        "extra",
    ],
)
def test_rejects_untrustworthy_evidence(weekly_evidence, mutation):
    from market_briefing.weekly.contracts import validate_weekly_document

    if mutation == "duplicate":
        weekly_evidence["observations"][1]["id"] = "o1"
    if mutation == "source":
        weekly_evidence["observations"][0]["source_id"] = "unknown"
    if mutation == "future_source":
        weekly_evidence["sources"][0]["published_at"] = "2026-10-04T00:00:00Z"
    if mutation == "future_known":
        weekly_evidence["scheduled_events"][0]["known_at"] = "2026-10-04T00:00:00Z"
    if mutation == "future_observation":
        weekly_evidence["observations"][0]["observed_at"] = "2026-10-04T00:00:00Z"
    if mutation == "event_window":
        weekly_evidence["events"][0]["event_at"] = "2026-09-27T00:00:00Z"
    if mutation == "collection":
        weekly_evidence["collected_at"] = "2026-10-02T00:00:00Z"
    if mutation == "week":
        weekly_evidence["week_start"] = "2026-09-29"
    if mutation == "nonfinite":
        weekly_evidence["observations"][0]["value"] = float("inf")
    if mutation == "extra":
        weekly_evidence["guessed_fact"] = True
    with pytest.raises(ValueError):
        validate_weekly_document(weekly_evidence, "weekly-evidence")


def test_analysis_links_and_absent_prior(weekly_evidence, weekly_analysis):
    from market_briefing.weekly.contracts import validate_weekly_analysis

    for field in ["claims", "selected_event_ids", "watchlist_ids", "comparison_ids"]:
        broken = copy.deepcopy(weekly_analysis)
        if field == "claims":
            broken[field][0]["evidence_ids"] = ["absent"]
        else:
            broken[field] = ["absent"]
        with pytest.raises(ValueError):
            validate_weekly_analysis(broken, weekly_evidence)
    weekly_analysis["previous_view"]["sha256"] = "a" * 64
    with pytest.raises(ValueError):
        validate_weekly_analysis(weekly_analysis, weekly_evidence)


def test_comparison_units_endpoints_and_staleness(weekly_evidence):
    from market_briefing.weekly.comparisons import calculate_comparison

    start, end = weekly_evidence["observations"]
    result = calculate_comparison(start, end, "return")
    assert result["value"] == 5
    assert result["unit"] == "percent"
    assert result["start_at"] == "2026-09-25T20:00:00Z"
    assert result["evidence_ids"] == ["o1", "o2"]
    start.update(value=4.0, unit="percent")
    end.update(value=4.1, unit="percent", endpoint_status="lagged")
    result = calculate_comparison(start, end, "yield_change")
    assert result["value"] == 10
    assert result["unit"] == "basis_points"
    assert result["stale"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("instrument", "OTHER"),
        ("contract", "OTHER"),
        ("adjustment", "adjusted"),
        ("unit", "usd"),
        ("observed_at", "2026-09-24T00:00:00Z"),
    ],
)
def test_incompatible_comparison(weekly_evidence, field, value):
    from market_briefing.weekly.comparisons import calculate_comparison

    start, end = weekly_evidence["observations"]
    end[field] = value
    with pytest.raises(ValueError):
        calculate_comparison(start, end, "return")
    start["value"] = 0
    with pytest.raises(ValueError):
        calculate_comparison(start, end, "return")
