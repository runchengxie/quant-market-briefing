"""Daily endpoint arithmetic with explicit identity and provenance."""

import copy
from decimal import Decimal
from pathlib import Path

from .artifacts import read_bounded
from .contracts import aware_time, validate_document
from .numeric_bindings import digest

EMPTY = {
    "schema_version": "market.comparison-input.v1",
    "sources": [],
    "endpoints": [],
    "requests": [],
}
IDENTITY = ("series_id", "instrument", "metric", "provider", "unit", "adjustment", "contract")


def load_comparison_input(path: Path | None, cutoff) -> dict:
    payload = read_bounded(path, path.parent)[0] if path is not None else copy.deepcopy(EMPTY)
    calculate_comparisons(payload, cutoff)
    return payload


def calculate_comparisons(payload: dict, cutoff) -> dict:
    validate_document(payload, "comparison-input")
    cutoff = aware_time(cutoff) if isinstance(cutoff, str) else cutoff
    if cutoff is None or cutoff.utcoffset() is None:
        raise ValueError("Comparison cutoff requires timezone")
    prefix = "history-" + digest(payload)[:16] + "-"
    sources, endpoints = copy.deepcopy(payload["sources"]), copy.deepcopy(payload["endpoints"])
    source_map, endpoint_map = {s["id"]: s for s in sources}, {e["id"]: e for e in endpoints}
    if len(source_map) != len(sources) or len(endpoint_map) != len(endpoints):
        raise ValueError("Duplicate comparison identities")
    for source in sources:
        if source["published_at"] is not None and aware_time(source["published_at"]) > cutoff:
            raise ValueError("Comparison source after cutoff")
    for endpoint in endpoints:
        if endpoint["source_id"] not in source_map:
            raise ValueError("Unknown comparison source")
        if endpoint["classification"] != "actual" or endpoint["verification"] != "verified":
            raise ValueError("Comparison requires verified actual endpoints")
        if not aware_time(endpoint["observed_at"]) <= aware_time(endpoint["known_at"]) <= cutoff:
            raise ValueError("Comparison endpoint outside cutoff")
        if not Decimal(str(endpoint["value"])).is_finite():
            raise ValueError("Non-finite endpoint")
        endpoint["id"], endpoint["source_id"] = (
            prefix + endpoint["id"],
            prefix + endpoint["source_id"],
        )
    for source in sources:
        source["id"] = prefix + source["id"]
    results, diagnostics, requests = [], [], set()
    for request in payload["requests"]:
        request_key = (request["start_id"], request["end_id"], request["method"])
        if request_key in requests:
            raise ValueError("Duplicate comparison request")
        requests.add(request_key)
        if any(key not in endpoint_map for key in request_key[:2]):
            diagnostics.append({"request": request, "code": "missing_endpoint"})
            continue
        start, end = (endpoint_map[key] for key in request_key[:2])
        if any(start[k] != end[k] for k in IDENTITY):
            raise ValueError("Comparison identity/basis mismatch")
        if aware_time(start["observed_at"]) >= aware_time(end["observed_at"]):
            raise ValueError("Comparison endpoint order")
        a, b = (Decimal(str(e["value"])) for e in [start, end])
        method, unit = request["method"], start["unit"]
        if method == "return":
            if unit not in {"usd", "index_level", "ratio"} or a <= 0 or b <= 0:
                raise ValueError("Return requires positive comparable price levels")
            value, unit, formula = (b / a - 1) * 100, "percent", "(end/start-1)*100"
        elif method == "yield_change":
            if unit != "percent":
                raise ValueError("Yield change requires percent levels")
            value, unit, formula = (b - a) * 100, "basis_points", "(end-start)*100"
        else:
            value, formula = b - a, "end-start"
            if unit == "percent":
                unit = "percentage_points"
        results.append(
            {
                "id": prefix + "derived-" + digest(request)[:16],
                "metric": start["metric"] + "_" + method,
                "value": float(value.quantize(Decimal("0.0001"))),
                "unit": unit,
                "method": method,
                "formula": formula,
                "evidence_ids": [start["id"], end["id"]],
                "source_id": end["source_id"],
                "start_at": start["observed_at"],
                "end_at": end["observed_at"],
                "reference_period": start["reference_period"] + "至" + end["reference_period"],
                "stale": any(e["endpoint_status"] == "lagged" for e in [start, end]),
            }
        )
    return {
        "schema_version": "market.comparisons.v1",
        "sources": sources,
        "endpoints": endpoints,
        "results": results,
        "diagnostics": diagnostics,
    }


def merge_comparisons(evidence: dict, comparisons: dict) -> dict:
    result = copy.deepcopy(evidence)
    incoming = []
    for e in comparisons["endpoints"]:
        incoming.append(
            {
                k: e[k]
                for k in [
                    "id",
                    "metric",
                    "value",
                    "unit",
                    "reference_period",
                    "classification",
                    "source_id",
                    "observed_at",
                    "verification",
                ]
            }
        )
    for e in comparisons["results"]:
        incoming.append(
            {
                **{
                    k: e[k]
                    for k in ["id", "metric", "value", "unit", "reference_period", "source_id"]
                },
                "classification": "actual",
                "verification": "verified",
                "observed_at": e["end_at"],
            }
        )
    for collection, items in [("sources", comparisons["sources"]), ("observations", incoming)]:
        known = {item["id"]: item for item in result[collection]}
        for item in items:
            if item["id"] in known and known[item["id"]] != item:
                raise ValueError("Comparison ID conflict")
            if item["id"] not in known:
                result[collection].append(copy.deepcopy(item))
                known[item["id"]] = item
    validate_document(result, "evidence")
    return result


def validate_comparison_claims(analysis: dict, comparisons: dict) -> None:
    derived = {r["id"]: set(r["evidence_ids"]) for r in comparisons["results"]}
    for claim in analysis["claims"]:
        linked = set(claim["evidence_ids"])
        for key in linked & derived.keys():
            if not derived[key] <= linked:
                raise ValueError("Derived claim must retain both endpoint references")
