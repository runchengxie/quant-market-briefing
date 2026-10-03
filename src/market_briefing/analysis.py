"""Fundamental-first analysis of frozen evidence."""
import json
from importlib.resources import files
from pathlib import Path

from .codex import execute_stage
from .contracts import schema_path, validate_document


def validate_analysis(analysis: dict, evidence: dict) -> None:
    validate_document(evidence, "evidence")
    validate_document(analysis, "analysis")
    observations = {item["id"]: item for item in evidence["observations"]}
    for claim in analysis["claims"]:
        if not set(claim["evidence_ids"]) <= observations.keys():
            raise ValueError(f"Unresolved evidence in {claim['id']}")
        linked = [observations[key] for key in claim["evidence_ids"]]
        if any(item["verification"] != "verified" or item["value"] is None for item in linked):
            raise ValueError(f"Unusable evidence in {claim['id']}")
        classes = {item["classification"] for item in linked}
        expected = next(iter(classes)) if len(classes) == 1 else "mixed"
        if claim["temporal_type"] != expected:
            raise ValueError(f"Claim changes actual/estimate classification: {claim['id']}")


def analyze(evidence: dict, config: dict) -> dict:
    validate_document(evidence, "evidence")
    instructions = files("market_briefing").joinpath("resources", "prompts", "analyst.md").read_text(encoding="utf-8")
    prompt = instructions + "\n\nFROZEN_EVIDENCE_JSON\n" + json.dumps(evidence, ensure_ascii=False)
    candidate = Path(config["run_dir"]) / "analysis.candidate.json"
    result = execute_stage(prompt, schema_path("analysis"), candidate, config.get("analyst_model"),
                           config.get("timeout_seconds", 600), Path(config["run_dir"]),
                           command_prefix=config.get("command_prefix"))
    validate_analysis(result, evidence)
    return result
