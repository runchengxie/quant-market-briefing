"""Structured daily stages, fixed criteria and one bounded corrective attempt."""

import copy
import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from .analysis import validate_analysis
from .codex import execute_stage
from .comparisons import EMPTY, calculate_comparisons, merge_comparisons, validate_comparison_claims
from .context import context_prompt
from .contracts import schema_path, validate_document
from .evidence_gates import apply_findings, freeze_requirements, validate_attempt
from .prior import load_prior
from .research import reconcile_revision
from .research_state import build_continuity, prepare_state, prior_conditions
from .storage import write_atomic


def _call(prompt, kind, name, config, role, live):
    return execute_stage(
        prompt,
        schema_path(kind),
        Path(config["run_dir"]) / name,
        config.get(role + "_model"),
        config.get("timeout_seconds", 1200),
        Path(config["run_dir"]),
        command_prefix=config.get("command_prefix"),
        reasoning_effort=config.get(role + "_effort"),
        web_search="live" if live else "disabled",
        require_search=live,
    )


def _instructions(config, evidence, prior, comparisons):
    resource = (
        files("market_briefing")
        .joinpath("resources/prompts/structured.zh-CN.md")
        .read_text(encoding="utf-8")
    )
    return (
        resource
        + "\nFROZEN_RESEARCH_DATA\n"
        + json.dumps(
            {
                "current": evidence,
                "prior": prior,
                "prior_conditions": list(prior_conditions(prior).values()),
                "comparisons": comparisons,
            },
            ensure_ascii=False,
        )
    )


def _reconcile(initial, candidate, run_dir=None, phase="challenge"):
    candidate = copy.deepcopy(candidate)
    candidate["research"], mapping = reconcile_revision(initial["research"], candidate["research"])
    rename = mapping["observations"]
    if run_dir is not None:
        write_atomic(Path(run_dir) / (phase + ".reconciliation.json"), mapping)
    for assessment in candidate["state"]["prior_conditions"]:
        assessment["evidence_ids"] = [rename.get(k, k) for k in assessment["evidence_ids"]]
    for question in candidate["questions"]["items"]:
        question["evidence_ids"] = [rename.get(k, k) for k in question["evidence_ids"]]
    return candidate


def _project(candidate, evidence, comparisons, prior, live):
    if live:
        payload = candidate["research"]
        evidence = {
            **evidence,
            "sources": payload["sources"],
            "observations": payload["observations"],
        }
        analysis = payload["analysis"]
    else:
        analysis = candidate["analysis"]
    evidence = merge_comparisons(evidence, comparisons)
    validate_analysis(analysis, evidence)
    validate_comparison_claims(analysis, comparisons)
    state = prepare_state(candidate["state"], analysis, evidence, prior)
    return evidence, analysis, state


def _finish(candidate, evidence, config, prior, comparisons, prompt, kind, requirements, live):
    members = {}
    for attempt in range(1, 3):
        evidence_current, analysis, state = _project(candidate, evidence, comparisons, prior, live)
        findings = validate_attempt(
            requirements, candidate["questions"], evidence_current, comparisons
        )
        record = {
            "status": "completed",
            "requirements": requirements,
            "candidate": copy.deepcopy(candidate),
            "findings": findings,
        }
        name = f"research-attempt-{attempt:04d}.json"
        write_atomic(Path(config["run_dir"]) / name, record)
        members[name] = record
        if not findings["blocked_horizons"] or attempt == 2:
            break
        correction = (
            prompt
            + "\n固定验收条件及失败记录，不得降低或替换条件\n"
            + json.dumps(record, ensure_ascii=False)
        )
        try:
            repaired = _call(
                correction,
                kind,
                "repair.candidate.json",
                config,
                "reviewer" if live else "analyst",
                live,
            )
            if live:
                repaired = _reconcile(candidate, repaired, config["run_dir"], "repair")
            # Validate criteria before accepting any corrected state.
            validate_attempt(
                requirements,
                repaired["questions"],
                _project(repaired, evidence, comparisons, prior, live)[0],
                comparisons,
            )
            candidate = repaired
        except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
            failed = {
                "status": "failed",
                "requirements": requirements,
                "candidate": None,
                "findings": findings,
                "error": str(exc),
            }
            write_atomic(Path(config["run_dir"]) / "research-attempt-0002.json", failed)
            members["research-attempt-0002.json"] = failed
            if isinstance(exc, ValueError):
                raise
            break
    state = apply_findings(state, findings)
    state = prepare_state(state, analysis, evidence_current, prior)
    members.update(
        {
            "prior-inventory.json": prior,
            "comparison-input.json": config.get("comparison_input", copy.deepcopy(EMPTY)),
            "comparisons.json": comparisons,
            "research-state.json": state,
            "continuity.json": build_continuity(prior, state),
            "research-questions.json": {
                "questions": candidate["questions"],
                "requirements": requirements,
                "findings": findings,
            },
        }
    )
    return evidence_current, analysis, members


def analyze_structured(evidence: dict, config: dict) -> tuple[dict, dict]:
    validate_document(evidence, "evidence")
    prior = config.get("prior", load_prior(None, evidence["market_date"], None))
    comparisons = calculate_comparisons(
        config.get("comparison_input", copy.deepcopy(EMPTY)), evidence["evidence_cutoff"]
    )
    evidence = merge_comparisons(evidence, comparisons)
    base = (
        files("market_briefing")
        .joinpath("resources/prompts/analyst.md")
        .read_text(encoding="utf-8")
    )
    prompt = base + "\n" + _instructions(config, evidence, prior, comparisons)
    candidate = _call(
        prompt, "analysis-structured", "analysis.candidate.json", config, "analyst", False
    )
    requirements = freeze_requirements(candidate["questions"])
    _, analysis, members = _finish(
        candidate,
        evidence,
        config,
        prior,
        comparisons,
        prompt,
        "analysis-structured",
        requirements,
        False,
    )
    return analysis, members


def research_structured(session: dict, cutoff: datetime, config: dict) -> tuple[dict, dict, dict]:
    context = {
        "schema_version": "market.evidence.v1",
        "market": "US",
        "market_date": session["market_date"],
        "timezone": "America/New_York",
        "scheduled_close": session["scheduled_close"],
        "evidence_cutoff": cutoff.isoformat(),
        "collected_at": cutoff.isoformat(),
    }
    prior = config.get("prior", load_prior(None, session["market_date"], None))
    comparisons = calculate_comparisons(
        config.get("comparison_input", copy.deepcopy(EMPTY)), cutoff
    )
    resources = files("market_briefing").joinpath("resources/prompts")
    prompt = (
        resources.joinpath("researcher.zh-CN.md").read_text(encoding="utf-8")
        + "\n"
        + resources.joinpath("research-framework.zh-CN.md").read_text(encoding="utf-8")
    )
    prompt += "\n" + _instructions(config, context, prior, comparisons)
    if config.get("research_context") is not None:
        prompt += context_prompt(config["research_context"])
    candidate = _call(
        prompt, "research-structured", "research.candidate.json", config, "analyst", True
    )
    _project(candidate, context, comparisons, prior, True)
    requirements = freeze_requirements(candidate["questions"])
    if config.get("research_depth", "standard") == "deep":
        write_atomic(Path(config["run_dir"]) / "research.initial.json", candidate)
        challenge = (
            resources.joinpath("challenger.zh-CN.md").read_text(encoding="utf-8") + "\n" + prompt
        )
        challenge += "\n待核查初稿与冻结验收条件\n" + json.dumps(
            {"candidate": candidate, "requirements": requirements}, ensure_ascii=False
        )
        revised = _call(
            challenge, "research-structured", "challenge.candidate.json", config, "reviewer", True
        )
        candidate = _reconcile(candidate, revised, config["run_dir"])
    context["collected_at"] = datetime.now(UTC).isoformat()
    return _finish(
        candidate,
        context,
        config,
        prior,
        comparisons,
        prompt,
        "research-structured",
        requirements,
        True,
    )
