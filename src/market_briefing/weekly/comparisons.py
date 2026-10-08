"""Explicit comparable endpoints and deterministic units."""

from decimal import Decimal

from ..contracts import aware_time


def calculate_comparison(start: dict, end: dict, method: str) -> dict:
    for field in ("instrument", "contract", "adjustment", "unit", "metric"):
        if start[field] != end[field]:
            raise ValueError(f"Incompatible comparison {field}")
    if not start["instrument"] or not start["adjustment"]:
        raise ValueError("Comparison requires instrument and adjustment identity")
    if any(
        item["verification"] != "verified" or item["classification"] != "realized"
        for item in (start, end)
    ):
        raise ValueError("Comparison requires verified realized endpoints")
    if aware_time(start["observed_at"]) >= aware_time(end["observed_at"]):
        raise ValueError("Comparison endpoints are reversed")
    if any(
        isinstance(item["value"], (str, bool)) or item["value"] is None for item in (start, end)
    ):
        raise ValueError("Comparison requires numeric endpoints")
    a, b = Decimal(str(start["value"])), Decimal(str(end["value"]))
    if not a.is_finite() or not b.is_finite():
        raise ValueError("Non-finite comparison")
    if method == "return":
        if start["unit"] not in {"usd", "index_level", "ratio"} or a <= 0 or b <= 0:
            raise ValueError("Return requires comparable positive price levels")
        value, unit, formula = (b / a - 1) * 100, "percent", "(end/start-1)*100"
    elif method == "yield_change" and start["unit"] == "percent":
        value, unit, formula = (b - a) * 100, "basis_points", "(end-start)*100"
    else:
        raise ValueError("Unsupported comparison method/unit")
    return {
        "id": f"cmp_{start['id']}_{end['id']}_{method}",
        "metric": start["metric"],
        "value": float(value.quantize(Decimal("0.0001"))),
        "unit": unit,
        "method": method,
        "formula": formula,
        "evidence_ids": [start["id"], end["id"]],
        "start_at": start["observed_at"],
        "end_at": end["observed_at"],
        "stale": any(item["endpoint_status"] == "lagged" for item in (start, end)),
    }
