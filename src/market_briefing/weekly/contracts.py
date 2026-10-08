"""Weekly schema, period and reference integrity; not source approval."""

import json
import math
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..contracts import aware_time, validate_document
from .calendar import select_week
from .comparisons import calculate_comparison

TOPICS = ["core", "macro", "events", "market_response", "next_week"]
COLLECTIONS = ["observations", "events", "scheduled_events", "comparisons"]


def validate_weekly_document(payload: dict, kind: str) -> None:
    validate_document(payload, kind)
    if kind == "weekly-evidence":
        start = datetime.combine(
            datetime.fromisoformat(payload["week_start"]).date(),
            time(),
            ZoneInfo(payload["timezone"]),
        )
        cutoff = aware_time(payload["evidence_cutoff"])
        end = aware_time(payload["week_end_exclusive"])
        retrospective = aware_time(payload["retrospective_end"])
        if (
            start.weekday() != 0
            or end != start + timedelta(days=7)
            or retrospective != min(end, cutoff)
        ):
            raise ValueError("Inconsistent weekly window")
        if cutoff < start + timedelta(days=4, hours=23, minutes=59, seconds=59):
            raise ValueError("Evidence cutoff precedes completed-week gate")
        if (
            aware_time(payload["scheduled_close"]) > cutoff
            or aware_time(payload["collected_at"]) < cutoff
        ):
            raise ValueError("Invalid close/collection cutoff")
        calendar_week = select_week(cutoff, payload["week_start"])
        for field in ["baseline_session", "final_session"]:
            if payload[field] != calendar_week.get(field):
                raise ValueError("Weekly session identity differs from exchange calendar")
        if aware_time(payload["scheduled_close"]) != aware_time(calendar_week["scheduled_close"]):
            raise ValueError("Weekly close differs from exchange calendar")
        sources = {item["id"]: item for item in payload["sources"]}
        all_ids = [item["id"] for name in COLLECTIONS for item in payload[name]]
        if len(sources) != len(payload["sources"]) or len(all_ids) != len(set(all_ids)):
            raise ValueError("Duplicate evidence identifiers")
        for source in sources.values():
            if source["published_at"] and aware_time(source["published_at"]) > cutoff:
                raise ValueError("Source published after evidence cutoff")
        observations = {item["id"]: item for item in payload["observations"]}
        for item in [*payload["observations"], *payload["scheduled_events"]]:
            if item["source_id"] not in sources:
                raise ValueError("Unresolved source ID")
            if aware_time(item["known_at"]) > cutoff:
                raise ValueError("Evidence known after cutoff")
        for item in observations.values():
            if aware_time(item["observed_at"]) > cutoff:
                raise ValueError("Observation after cutoff")
            value = item["value"]
            if value is not None and isinstance(value, str) != (item["unit"] == "text"):
                raise ValueError("Value/unit mismatch")
            if isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError("Non-finite observation")
        for item in payload["events"]:
            if (
                not start <= aware_time(item["event_at"]) < retrospective
                or aware_time(item["known_at"]) > cutoff
            ):
                raise ValueError("Event outside retrospective window/cutoff")
            if not set(item["evidence_ids"]) <= observations.keys():
                raise ValueError("Unresolved event observation")
        for item in payload["scheduled_events"]:
            if not end <= aware_time(item["event_at"]) < end + timedelta(days=7):
                raise ValueError("Scheduled event is not in next week")
        for item in payload["comparisons"]:
            if (
                len(item["evidence_ids"]) != 2
                or not set(item["evidence_ids"]) <= observations.keys()
            ):
                raise ValueError("Unresolved comparison endpoints")
            expected = calculate_comparison(
                *(observations[key] for key in item["evidence_ids"]), item["method"]
            )
            if item != expected:
                raise ValueError("Comparison differs from computed endpoints")
            for key, expected_day in zip(
                item["evidence_ids"],
                [payload["baseline_session"], payload["final_session"]],
                strict=True,
            ):
                observation = observations[key]
                actual_day = (
                    aware_time(observation["observed_at"])
                    .astimezone(ZoneInfo(payload["timezone"]))
                    .date()
                    .isoformat()
                )
                if observation["endpoint_status"] == "complete" and actual_day != expected_day:
                    raise ValueError("Completed comparison endpoint is not the weekly session date")
                if actual_day > expected_day:
                    raise ValueError("Comparison endpoint extends beyond its weekly session")
    elif kind in {"weekly-analysis", "weekly-editor", "weekly-briefing"}:
        if [s["topic"] for s in payload["sections"]] != TOPICS:
            raise ValueError("Weekly sections missing or out of order")
        if kind != "weekly-editor":
            prior = payload["previous_view"]
            if prior["status"] == "absent" and (
                prior["sha256"] is not None or prior["week_start"] is not None
            ):
                raise ValueError("Absent prior view has an identity")
            if prior["status"] == "available" and (
                prior["sha256"] is None or prior["week_start"] is None
            ):
                raise ValueError("Available prior view lacks identity")
        if kind == "weekly-briefing" and payload["brief_text"] != render_sections(
            payload["sections"]
        ):
            raise ValueError("brief_text differs from sections")
    elif kind == "weekly-review":
        ids = [item["claim_id"] for item in payload["decisions"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate review decisions")


def render_sections(sections: list[dict]) -> str:
    return "\n\n".join(f"{section['heading']}\n{section['text']}" for section in sections)


def linked_records(ids: list[str], evidence: dict) -> list[dict]:
    records = {item["id"]: item for name in COLLECTIONS for item in evidence[name]}
    found = {}

    def visit(key):
        if key not in records:
            raise ValueError("Unresolved claim evidence")
        if key in found:
            return
        record = records[key]
        found[key] = record
        for reference in record.get("evidence_ids", []):
            visit(reference)

    for key in ids:
        visit(key)
    return list(found.values())


def validate_weekly_analysis(analysis: dict, evidence: dict) -> None:
    validate_weekly_document(evidence, "weekly-evidence")
    validate_weekly_document(analysis, "weekly-analysis")
    known = {item["id"]: item for name in COLLECTIONS for item in evidence[name]}
    claims = {item["id"]: item for item in analysis["claims"]}
    if len(claims) != len(analysis["claims"]):
        raise ValueError("Duplicate claim identifiers")
    for claim in claims.values():
        if not set(claim["evidence_ids"]) <= known.keys():
            raise ValueError("Unresolved claim evidence")
        records = linked_records(claim["evidence_ids"], evidence)
        temporal = set()
        for observation in records:
            if "verification" in observation and (
                observation["verification"] != "verified" or observation["value"] is None
            ):
                raise ValueError("Claim uses unverified/missing observation")
            if "classification" in observation:
                temporal.add(observation["classification"])
            elif "status" in observation:
                temporal.add("scheduled")
        expected_temporal = (
            "scheduled"
            if "scheduled" in temporal
            else "mixed"
            if temporal == {"realized", "estimate"}
            else next(iter(temporal))
        )
        if claim["temporal_type"] != expected_temporal:
            raise ValueError("Claim temporal classification differs from supporting evidence")
    if any(not set(s["claim_ids"]) <= claims.keys() for s in analysis["sections"]):
        raise ValueError("Unresolved section claim")
    for name, field in [
        ("events", "selected_event_ids"),
        ("scheduled_events", "watchlist_ids"),
        ("comparisons", "comparison_ids"),
    ]:
        if not set(analysis[field]) <= {item["id"] for item in evidence[name]}:
            raise ValueError("Unresolved analysis selection")
    previous = analysis["previous_view"]
    if previous["status"] == "available" and previous["week_start"] >= evidence["week_start"]:
        raise ValueError("Previous view is not from an earlier week")


def load_weekly_document(path: Path, kind: str) -> dict:
    def reject(value):
        raise ValueError(f"Nonfinite JSON constant {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    validate_weekly_document(payload, kind)
    return payload
