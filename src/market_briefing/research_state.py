"""Structured judgments and descriptive continuity, never outcome scoring."""

import copy

from .contracts import aware_time, validate_document
from .numeric_bindings import digest

HORIZONS = {"short_term": "1-4w", "long_term": "6-12m"}


def condition_id(origin: str, text: str) -> str:
    return "condition-" + digest({"origin": origin, "text": text})[:24]


def prior_conditions(prior: dict) -> dict:
    documents = prior.get("documents", {})
    state = documents.get("research-state")
    if state:
        result = {c["id"]: c for h in HORIZONS for c in state[h]["conditions"]}
        # Keep retired/unresolved history available without resurrecting it as a new condition.
        for c in state.get("prior_conditions", []):
            if "text" in c and c["id"] not in result:
                result[c["id"]] = c
        return result
    identity = prior.get("identity") or {}
    origin = identity.get("run_id", "") + ":" + identity.get("analysis_sha256", "")
    return {
        condition_id(origin, text): {
            "id": condition_id(origin, text),
            "text": text,
            "origin": origin,
        }
        for text in documents.get("analysis", {}).get("invalidation_conditions", [])
    }


def prepare_state(state: dict, analysis: dict, evidence: dict, prior: dict) -> dict:
    result = copy.deepcopy(state)
    origin = evidence["market_date"] + ":" + digest(analysis)
    represented = {c["text"] for h in HORIZONS for c in result[h]["conditions"]}
    for text in analysis["invalidation_conditions"]:
        if text not in represented:
            result["long_term"]["conditions"].append({"id": "", "origin": "", "text": text})
            represented.add(text)
    for horizon in HORIZONS:
        for condition in result[horizon]["conditions"]:
            if not condition.get("id") and not condition.get("origin"):
                condition.update(origin=origin, id=condition_id(origin, condition["text"]))
    known = prior_conditions(prior)
    for assessment in result["prior_conditions"]:
        if assessment["id"] in known:
            if any(
                k in assessment and assessment[k] != known[assessment["id"]][k]
                for k in ["text", "origin"]
            ):
                raise ValueError("Changed historical condition")
            assessment.update(
                text=known[assessment["id"]]["text"], origin=known[assessment["id"]]["origin"]
            )
    validate_state(result, analysis, evidence, prior)
    return result


def validate_state(state: dict, analysis: dict, evidence: dict, prior: dict) -> None:
    validate_document(state, "research-state")
    claims = {c["id"] for c in analysis["claims"]}
    observations = {o["id"]: o for o in evidence["observations"]}
    known = prior_conditions(prior)
    seen = set()
    for name, horizon in HORIZONS.items():
        view = state[name]
        if view["horizon"] != horizon or not set(view["claim_ids"]) <= claims:
            raise ValueError("Invalid horizon/current claim reference")
        if view["assessment_status"] == "insufficient":
            if (
                view["direction"] is not None
                or view["confidence"] is not None
                or not view["gap"].strip()
            ):
                raise ValueError("Insufficient assessment is not neutral")
        elif view["direction"] is None or view["confidence"] is None or not view["claim_ids"]:
            raise ValueError("Available assessment needs direction, confidence and evidence")
        elif name == "long_term" and any(
            view[k] != analysis["thesis"][k if k != "direction" else "stance"]
            for k in ["direction", "confidence"]
        ):
            raise ValueError("Structured long-term view differs from public thesis")
        for condition in view["conditions"]:
            if condition["id"] in seen or condition["id"] != condition_id(
                condition["origin"], condition["text"]
            ):
                raise ValueError("Invalid or duplicate condition identity")
            seen.add(condition["id"])
            if condition["id"] in known and any(
                condition[k] != known[condition["id"]][k] for k in ["origin", "text"]
            ):
                raise ValueError("Prior condition changed meaning")
            if condition["id"] not in known and condition["origin"] != evidence[
                "market_date"
            ] + ":" + digest(analysis):
                raise ValueError("New condition has a foreign origin")
    assessments = state["prior_conditions"]
    if len({c["id"] for c in assessments}) != len(assessments) or {
        c["id"] for c in assessments
    } != set(known):
        raise ValueError("Every prior condition requires an explicit assessment")
    for item in assessments:
        keys = item["evidence_ids"]
        if not set(keys) <= observations.keys():
            raise ValueError("Unknown condition evidence")
        if any(
            observations[k]["verification"] != "verified" or observations[k]["value"] is None
            for k in keys
        ):
            raise ValueError("Unusable condition evidence")
        if item["status"] in {"observed", "not_observed"} and not keys:
            raise ValueError("Observed condition requires current evidence")
        if item["status"] in {"observed", "not_observed"} and any(
            observations[k]["classification"] != "actual" for k in keys
        ):
            raise ValueError("Observed condition cannot use estimates as outcomes")
        if item["status"] == "not_observed":
            # Public evidence v1 records point observations, not interval completeness.
            # A model-declared window cannot prove absence throughout that interval.
            raise ValueError("Negative observation needs interval coverage; retain unresolved")
        if item["window"] is not None:
            start, end = (aware_time(item["window"][k]) for k in ["start", "end"])
            if not start < end <= aware_time(evidence["evidence_cutoff"]):
                raise ValueError("Invalid condition observation window")
        for k in ["text", "origin"]:
            if k in item and item[k] != known[item["id"]][k]:
                raise ValueError("Changed historical condition")


def build_continuity(prior: dict, state: dict) -> dict:
    result = {"schema_version": "market.research-continuity.v1", "prior_status": prior["status"]}
    old_state = prior.get("documents", {}).get("research-state", {})
    for name in HORIZONS:
        old = old_state.get(name)
        if old is None and name == "long_term" and prior.get("documents", {}).get("analysis"):
            thesis = prior["documents"]["analysis"]["thesis"]
            old = {
                "assessment_status": "available",
                "direction": thesis["stance"],
                "confidence": thesis["confidence"],
            }
        current = state[name]
        change = "unavailable"
        direction_changed = confidence_changed = False
        if old:
            a, b = old["assessment_status"], current["assessment_status"]
            if a != b:
                change = "became_assessable" if b == "available" else "became_insufficient"
            elif b == "available":
                direction_changed = old["direction"] != current["direction"]
                confidence_changed = old["confidence"] != current["confidence"]
                change = "changed" if direction_changed or confidence_changed else "unchanged"
        result[name] = {
            "change": change,
            "direction_changed": direction_changed,
            "confidence_changed": confidence_changed,
            "current_claim_ids": current["claim_ids"],
        }
    return result
