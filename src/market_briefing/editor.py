"""Chinese editing stage with trusted metadata assembly."""

import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from .analysis import validate_analysis
from .codex import execute_stage
from .contracts import schema_path, validate_document
from .numeric_bindings import RECORD_NAME, binding_marker, render_candidate
from .storage import write_atomic
from .validate import validate_draft


def assemble_briefing(
    output: dict,
    evidence: dict,
    analysis: dict,
    run_id: str,
    revision: int,
    *,
    bindings: dict | None = None,
) -> dict:
    validate_document(output, "editor")
    validate_analysis(analysis, evidence)
    brief = {
        "schema_version": "market.briefing.v1",
        "market": "US",
        "market_date": evidence["market_date"],
        "evidence_cutoff": evidence["evidence_cutoff"],
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "revision": revision,
        "status": "draft",
        "headline": output["headline"],
        "paragraphs": output["paragraphs"],
        "brief_text": "\n\n".join(p["text"] for p in output["paragraphs"]),
        "thesis": analysis["thesis"],
        "sources": evidence["sources"],
        "quality": {
            "structure_passed": True,
            "evidence_links_passed": False,
            "editorial_rules_passed": False,
            "source_audit_passed": False,
            "errors": [],
            "warnings": [binding_marker(bindings)] if bindings is not None else [],
        },
    }
    quality = validate_draft(evidence, analysis, brief, bindings=bindings)
    brief["quality"] = quality
    if not quality["errors"]:
        brief["status"] = "validated_draft"
    return brief


def edit(analysis: dict, evidence: dict, config: dict) -> dict:
    validate_analysis(analysis, evidence)
    instructions = (
        files("market_briefing")
        .joinpath("resources", "prompts", "editor.zh-CN.md")
        .read_text(encoding="utf-8")
    )
    prompt = (
        instructions
        + "\n\nFROZEN_INPUT_JSON\n"
        + json.dumps({"analysis": analysis, "evidence": evidence}, ensure_ascii=False)
    )
    output = execute_stage(
        prompt,
        schema_path("editor"),
        Path(config["run_dir"]) / "editor.candidate.json",
        config.get("editor_model"),
        config.get("timeout_seconds", 600),
        Path(config["run_dir"]),
        command_prefix=config.get("command_prefix"),
        reasoning_effort=config.get("editor_effort"),
    )
    rendered, bindings = render_candidate(output, evidence, analysis)
    write_atomic(Path(config["run_dir"]) / RECORD_NAME, bindings)
    return assemble_briefing(
        rendered,
        evidence,
        analysis,
        config["run_id"],
        config["revision"],
        bindings=bindings,
    )
