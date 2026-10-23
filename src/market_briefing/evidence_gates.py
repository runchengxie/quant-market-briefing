"""Declared evidence criteria; semantic relevance still requires review."""

import copy

from .contracts import validate_document


def freeze_requirements(questions: dict) -> dict:
    validate_document(questions, "research-questions")
    result = {
        q["id"]: {k: copy.deepcopy(q[k]) for k in ["relevance", "horizons", "requirements"]}
        for q in questions["items"]
    }
    if len(result) != len(questions["items"]):
        raise ValueError("Duplicate research question")
    return result


def validate_questions(questions: dict, evidence: dict, comparisons: dict) -> dict:
    freeze_requirements(questions)
    observations = {o["id"]: o for o in evidence["observations"]}
    endpoints = {e["id"]: e for e in comparisons["endpoints"]}
    results = {r["id"]: r for r in comparisons["results"]}
    findings = []
    for q in questions["items"]:
        errors = []
        req = q["requirements"]
        selected = []
        if len(set(q["evidence_ids"])) < req["minimum"]:
            errors.append("insufficient_observations")
        for key in q["evidence_ids"]:
            o = observations.get(key)
            if o is None:
                errors.append("unknown_evidence")
                continue
            selected.append(o)
            if req["complete"] and key not in endpoints:
                errors.append("coverage_unknown")
            if o["verification"] != "verified" or o["value"] is None:
                errors.append("unusable_evidence")
            if req["classification"] != "any" and o["classification"] != req["classification"]:
                errors.append("classification_mismatch")
        compared = []
        for key in q["comparison_ids"]:
            r = results.get(key)
            if r is None or not set(r["evidence_ids"]) <= set(q["evidence_ids"]):
                errors.append("incomplete_comparison")
                continue
            compared.append(r)
            if req["complete"] and r["stale"]:
                errors.append("stale_comparison")
        if req["kind"] == "comparison" and not compared:
            errors.append("comparison_required")
        series = {endpoints[o["id"]]["series_id"] for o in selected if o["id"] in endpoints}
        if not set(req["series_ids"]) <= series:
            errors.append("series_coverage")
        if not set(req["reference_periods"]) <= {o["reference_period"] for o in selected}:
            errors.append("period_coverage")
        if req["complete"] and any(
            endpoints[o["id"]]["endpoint_status"] != "complete"
            for o in selected
            if o["id"] in endpoints
        ):
            errors.append("stale_endpoint")
        findings.append(
            {
                "id": q["id"],
                "passed": not errors,
                "horizons": q["horizons"],
                "errors": sorted(set(errors)),
            }
        )
    return {
        "schema_version": "market.evidence-findings.v1",
        "items": findings,
        "blocked_horizons": sorted(
            {h for item in findings if not item["passed"] for h in item["horizons"]}
        ),
    }


def validate_attempt(
    original_requirements: dict, candidate: dict, evidence: dict, comparisons: dict
) -> dict:
    if freeze_requirements(candidate) != original_requirements:
        raise ValueError("Research repair cannot weaken or change original requirements")
    return validate_questions(candidate, evidence, comparisons)


def apply_findings(state: dict, findings: dict) -> dict:
    result = copy.deepcopy(state)
    for horizon in findings["blocked_horizons"]:
        gaps = [
            item["id"] + ":" + ",".join(item["errors"])
            for item in findings["items"]
            if not item["passed"] and horizon in item["horizons"]
        ]
        result[horizon].update(
            assessment_status="insufficient",
            direction=None,
            confidence=None,
            path="当前证据不足，暂不可判断。",
            gap="; ".join(gaps),
        )
    return result
