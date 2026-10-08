"""Frozen-input Chinese editor and trusted weekly assembly."""

import copy
import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from ..codex import execute_stage
from ..contracts import schema_path
from .contracts import render_sections, validate_weekly_analysis, validate_weekly_document
from .validate import validate_weekly_draft


def assemble_weekly_briefing(
    output: dict, evidence: dict, analysis: dict, run_id: str, revision: int
) -> dict:
    validate_weekly_document(output, "weekly-editor")
    validate_weekly_analysis(analysis, evidence)
    briefing = copy.deepcopy(
        {
            "schema_version": "market.weekly-briefing.v1",
            "market": "US",
            "product": "weekly",
            **{
                key: evidence[key]
                for key in [
                    "week_start",
                    "week_end_exclusive",
                    "retrospective_end",
                    "timezone",
                    "evidence_cutoff",
                ]
            },
            "generated_at": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "revision": revision,
            "status": "draft",
            "headline": output["headline"],
            "sections": output["sections"],
            "brief_text": render_sections(output["sections"]),
            "thesis": analysis["thesis"],
            "previous_view": analysis["previous_view"],
            "sources": evidence["sources"],
            "missing_inputs": list(
                dict.fromkeys([*evidence["missing_inputs"], *analysis["missing_inputs"]])
            ),
            "quality": {
                "structure_passed": True,
                "evidence_links_passed": False,
                "editorial_rules_passed": False,
                "source_audit_passed": False,
                "errors": [],
                "warnings": [],
            },
        }
    )
    briefing["quality"] = validate_weekly_draft(evidence, analysis, briefing)
    if not briefing["quality"]["errors"]:
        briefing["status"] = "validated_draft"
    return briefing


def edit_week(analysis: dict, evidence: dict, config: dict) -> dict:
    validate_weekly_analysis(analysis, evidence)
    prompt = (
        files("market_briefing")
        .joinpath("resources/prompts/weekly-editor.zh-CN.md")
        .read_text(encoding="utf-8")
    )
    prompt += "\n\nFROZEN_INPUT_JSON\n" + json.dumps(
        {"evidence": evidence, "analysis": analysis}, ensure_ascii=False
    )
    run_dir = Path(config["run_dir"])
    # A failed edit may leave a candidate: keep it and choose another immutable stage filename.
    index = 1
    output = run_dir / "editor.candidate.json"
    while output.exists():
        index += 1
        output = run_dir / f"editor.candidate-{index}.json"
    result = execute_stage(
        prompt,
        schema_path("weekly-editor"),
        output,
        config.get("editor_model", "gpt-6.1-sol"),
        config.get("timeout_seconds", 1200),
        run_dir,
        command_prefix=config.get("command_prefix"),
        web_search="disabled",
        reasoning_effort=config.get("editor_effort", "medium"),
    )
    return assemble_weekly_briefing(
        result, evidence, analysis, config["run_id"], config["revision"]
    )
