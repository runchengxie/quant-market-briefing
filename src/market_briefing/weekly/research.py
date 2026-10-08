"""Live weekly research with frozen, reconciled evidence."""

import copy
import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from ..codex import execute_stage
from ..contracts import schema_path
from ..storage import write_atomic
from .comparisons import calculate_comparison
from .contracts import validate_weekly_analysis, validate_weekly_document


def group_events(events: list[dict]) -> dict:
    groups = {}
    for event in sorted(events, key=lambda item: (item["event_at"], item["id"])):
        groups.setdefault(event["topic_key"], []).append(event)
    return groups


def reconcile_weekly_revision(initial: dict, candidate: dict) -> tuple[dict, dict]:
    validate_weekly_document(candidate, "weekly-research")
    revised = copy.deepcopy(candidate)
    mapping = {}
    for collection in ["sources", "observations", "events", "scheduled_events"]:
        originals = {item["id"]: item for item in initial[collection]}
        identifiers = [item["id"] for item in revised[collection]]
        if len(originals) != len(initial[collection]) or len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate IDs cannot be reconciled")
        used = set(originals) | set(identifiers)
        changed = {}
        for item in revised[collection]:
            old = item["id"]
            if old in originals and item != originals[old]:
                suffix = 1
                while f"{old}_revision_{suffix}" in used:
                    suffix += 1
                fresh = f"{old}_revision_{suffix}"
                item["id"] = fresh
                changed[old] = fresh
                used.add(fresh)
        mapping[collection] = changed
        # Update dependent records before deciding whether their identities changed.
        for name in ["observations", "events", "scheduled_events"]:
            for item in revised[name]:
                if "source_id" in item and collection == "sources":
                    item["source_id"] = changed.get(item["source_id"], item["source_id"])
                if "evidence_ids" in item and collection == "observations":
                    item["evidence_ids"] = [changed.get(key, key) for key in item["evidence_ids"]]
        for claim in revised["analysis"]["claims"]:
            claim["evidence_ids"] = [changed.get(key, key) for key in claim["evidence_ids"]]
        field = {"events": "selected_event_ids", "scheduled_events": "watchlist_ids"}.get(
            collection
        )
        if field:
            revised["analysis"][field] = [
                changed.get(key, key) for key in revised["analysis"][field]
            ]
        if collection == "observations":
            for request in revised["comparison_requests"]:
                request["start_id"] = changed.get(request["start_id"], request["start_id"])
                request["end_id"] = changed.get(request["end_id"], request["end_id"])

            def comparison_id(key, changes=changed):
                for old, fresh in changes.items():
                    key = key.replace(f"cmp_{old}_", f"cmp_{fresh}_").replace(
                        f"_{old}_", f"_{fresh}_"
                    )
                return key

            revised["analysis"]["comparison_ids"] = [
                comparison_id(key) for key in revised["analysis"]["comparison_ids"]
            ]
            for claim in revised["analysis"]["claims"]:
                claim["evidence_ids"] = [comparison_id(key) for key in claim["evidence_ids"]]
    return revised, mapping


def assemble_weekly_research(result: dict, metadata: dict, context: dict) -> tuple[dict, dict]:
    validate_weekly_document(result, "weekly-research")
    observations = {item["id"]: item for item in result["observations"]}
    comparisons = []
    for request in result["comparison_requests"]:
        if request["start_id"] not in observations or request["end_id"] not in observations:
            raise ValueError("Unresolved comparison request")
        comparisons.append(
            calculate_comparison(
                observations[request["start_id"]],
                observations[request["end_id"]],
                request["method"],
            )
        )
    evidence = {
        **metadata,
        **{
            key: result[key]
            for key in ["sources", "observations", "events", "scheduled_events", "missing_inputs"]
        },
        "comparisons": comparisons,
    }
    evidence["missing_inputs"] = list(
        dict.fromkeys([*evidence["missing_inputs"], *context.get("missing_inputs", [])])
    )
    analysis = copy.deepcopy(result["analysis"])
    previous = context.get(
        "previous_view",
        {
            "status": "absent",
            "week_start": None,
            "sha256": None,
            "comparison": "无上周报告可比较。",
        },
    )
    if previous["status"] == "available":
        analysis["previous_view"].update(
            status="available", week_start=previous["week_start"], sha256=previous["sha256"]
        )
    else:
        analysis["previous_view"] = {
            key: previous[key] for key in ["status", "week_start", "sha256", "comparison"]
        }
    validate_weekly_analysis(analysis, evidence)
    return evidence, analysis


def research_week(week: dict, cutoff: datetime, config: dict) -> tuple[dict, dict]:
    run_dir = Path(config["run_dir"])
    metadata = {
        "schema_version": "market.weekly-evidence.v1",
        "market": "US",
        "product": "weekly",
        **{
            key: week[key]
            for key in [
                "week_start",
                "week_end_exclusive",
                "retrospective_end",
                "timezone",
                "baseline_session",
                "final_session",
                "scheduled_close",
            ]
        },
        "evidence_cutoff": cutoff.isoformat(),
        "collected_at": cutoff.isoformat(),
    }
    context = config.get("weekly_context", {})
    resources = files("market_briefing").joinpath("resources", "prompts")
    prompt = resources.joinpath("weekly-researcher.zh-CN.md").read_text(encoding="utf-8")
    prompt += "\n\nTRUSTED_WEEK_METADATA\n" + json.dumps(metadata, ensure_ascii=False)
    prompt += "\n\nUNTRUSTED_CONTEXT_DATA\n" + json.dumps(context, ensure_ascii=False)

    def invoke(instructions, output, stage):
        return execute_stage(
            instructions,
            schema_path("weekly-research"),
            run_dir / output,
            config.get(f"{stage}_model", "gpt-6-astra"),
            config.get("timeout_seconds", 1200),
            run_dir,
            command_prefix=config.get("command_prefix"),
            web_search="live",
            require_search=True,
            reasoning_effort=config.get(
                f"{stage}_effort", "xhigh" if stage == "analyst" else "high"
            ),
        )

    result = invoke(prompt, "research.candidate.json", "analyst")
    assemble_weekly_research(result, metadata, context)
    write_atomic(run_dir / "research.initial.json", result)
    if config.get("research_depth", "deep") == "deep":
        challenge = resources.joinpath("weekly-challenger.zh-CN.md").read_text(encoding="utf-8")
        challenge += (
            "\n\n"
            + prompt
            + "\n\nUNREVIEWED_INITIAL_RESEARCH\n"
            + json.dumps(result, ensure_ascii=False)
        )
        candidate = invoke(challenge, "challenge.candidate.json", "reviewer")
        result, mapping = reconcile_weekly_revision(result, candidate)
        write_atomic(run_dir / "challenge.reconciliation.json", mapping)
    metadata["collected_at"] = datetime.now(UTC).isoformat()
    # Tests/replay may inject a future research clock; retain the contractual ordering.
    if datetime.fromisoformat(metadata["collected_at"]) < cutoff:
        metadata["collected_at"] = cutoff.isoformat()
    evidence, analysis = assemble_weekly_research(result, metadata, context)
    write_atomic(run_dir / "event-groups.json", group_events(evidence["events"]))
    return evidence, analysis
