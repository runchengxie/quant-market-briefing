import copy

import pytest

from market_briefing.comparisons import calculate_comparisons, merge_comparisons


@pytest.fixture
def comparison_input(evidence):
    endpoint = {
        "series_id": "synthetic-index",
        "instrument": "synthetic",
        "metric": "level",
        "provider": "synthetic",
        "unit": "index_level",
        "adjustment": "published",
        "contract": None,
        "value": 100,
        "source_id": "s1",
        "observed_at": "2026-10-01T20:00:00Z",
        "known_at": "2026-10-01T21:00:00Z",
        "reference_period": "2026-10-01",
        "verification": "verified",
        "classification": "actual",
        "endpoint_status": "complete",
        "id": "start",
    }
    end = {
        **endpoint,
        "id": "end",
        "value": 110,
        "observed_at": "2026-10-02T20:00:00Z",
        "known_at": "2026-10-02T21:00:00Z",
        "reference_period": "2026-10-02",
    }
    sources = copy.deepcopy(evidence["sources"])
    sources[0]["published_at"] = "2026-10-01T20:30:00Z"
    return {
        "schema_version": "market.comparison-input.v1",
        "sources": sources,
        "endpoints": [endpoint, end],
        "requests": [{"start_id": "start", "end_id": "end", "method": "return"}],
    }


@pytest.mark.parametrize(
    "method,unit,a,b,value,result_unit",
    [
        ("return", "index_level", 100, 110, 10, "percent"),
        ("yield_change", "percent", 4, 4.25, 25, "basis_points"),
        ("absolute_change", "percent", 1, 3, 2, "percentage_points"),
    ],
)
def test_arithmetic(comparison_input, method, unit, a, b, value, result_unit):
    comparison_input["requests"][0]["method"] = method
    for endpoint, number in zip(comparison_input["endpoints"], [a, b], strict=True):
        endpoint.update(unit=unit, value=number)
    result = calculate_comparisons(comparison_input, "2026-10-02T22:00:00Z")["results"][0]
    assert (result["value"], result["unit"]) == (value, result_unit)


@pytest.mark.parametrize(
    "field,value",
    [
        ("instrument", "other"),
        ("provider", "other"),
        ("contract", "future"),
        ("adjustment", "other"),
        ("classification", "estimate"),
        ("value", float("nan")),
        ("observed_at", "2026-09-30T20:00:00Z"),
        ("known_at", "2026-10-03T20:00:00Z"),
    ],
)
def test_invalid_endpoints_rejected(comparison_input, field, value):
    comparison_input["endpoints"][1][field] = value
    with pytest.raises(ValueError):
        calculate_comparisons(comparison_input, "2026-10-02T22:00:00Z")


def test_missing_and_lagged_not_zero(comparison_input):
    comparison_input["endpoints"][1]["endpoint_status"] = "lagged"
    assert calculate_comparisons(comparison_input, "2026-10-02T22:00:00Z")["results"][0]["stale"]
    comparison_input["endpoints"].pop()
    result = calculate_comparisons(comparison_input, "2026-10-02T22:00:00Z")
    assert result["results"] == [] and result["diagnostics"]


def test_derived_provenance_and_collision_safe_merge(comparison_input, evidence):
    before = copy.deepcopy(evidence)
    result = calculate_comparisons(comparison_input, evidence["evidence_cutoff"])
    merged = merge_comparisons(evidence, result)
    assert evidence == before
    ids = {o["id"] for o in merged["observations"]}
    assert set(result["results"][0]["evidence_ids"]) <= ids
    assert result["results"][0]["id"] in ids


def test_extreme_finite_arithmetic_has_controlled_error(comparison_input):
    comparison_input["endpoints"][0]["value"] = 1e-300
    comparison_input["endpoints"][1]["value"] = 1e300
    with pytest.raises(ValueError, match="range"):
        calculate_comparisons(comparison_input, "2026-10-02T22:00:00Z")
