"""Live web research, with source records frozen before editing."""

import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from .analysis import validate_analysis
from .codex import execute_stage
from .contracts import schema_path, validate_document


def assemble_research(result: dict, context: dict) -> tuple[dict, dict]:
    validate_document(result, "research")
    evidence = {**context, "sources": result["sources"], "observations": result["observations"]}
    validate_document(evidence, "evidence")
    validate_analysis(result["analysis"], evidence)
    return evidence, result["analysis"]


def research(session: dict, cutoff: datetime, config: dict) -> tuple[dict, dict]:
    context = {
        "schema_version": "market.evidence.v1",
        "market": "US",
        "market_date": session["market_date"],
        "timezone": "America/New_York",
        "scheduled_close": session["scheduled_close"],
        "evidence_cutoff": cutoff.isoformat(),
        "collected_at": cutoff.isoformat(),
    }
    resources = files("market_briefing").joinpath("resources", "prompts")
    prompt = resources.joinpath("researcher.zh-CN.md").read_text(encoding="utf-8")
    prompt += "\n\n原始投研框架\n" + resources.joinpath("research-framework.zh-CN.md").read_text(
        encoding="utf-8"
    )
    prompt += "\n\n任务上下文\n" + json.dumps(context, ensure_ascii=False)
    result = execute_stage(
        prompt,
        schema_path("research"),
        Path(config["run_dir"]) / "research.candidate.json",
        config.get("analyst_model"),
        config.get("timeout_seconds", 600),
        Path(config["run_dir"]),
        command_prefix=config.get("command_prefix"),
        web_search="live",
        require_search=True,
    )
    context["collected_at"] = datetime.now(UTC).isoformat()
    return assemble_research(result, context)
