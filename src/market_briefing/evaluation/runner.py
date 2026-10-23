"""Offline by default experiments with immutable, non-publishable outputs."""

import copy
import json
import subprocess
import time
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from ..analysis import validate_analysis
from ..codex import execute_stage
from ..contracts import schema_path
from ..editor import assemble_briefing, edit
from ..numeric_bindings import digest, render_candidate
from ..research_state import validate_state
from ..storage import assert_external_path, write_atomic
from .metrics import summarize

DEFAULT_SETTINGS = {
    "analyst_model": "gpt-6-astra",
    "analyst_effort": "xhigh",
    "reviewer_model": "gpt-6-astra",
    "reviewer_effort": "high",
    "editor_model": "gpt-6.1-sol",
    "editor_effort": "medium",
    "timeout_seconds": 1200,
}


def _fingerprint(record):
    rows = record.get("bindings", []) if record else []
    values = sorted(
        (r["observation_id"], r["metric"], str(r["value"]), r["unit"], r["reference_period"])
        for r in rows
    )
    return digest({"quantities": values}) if values else None


def _bound(candidate, evidence, analysis):
    output, record = render_candidate(candidate, evidence, analysis)
    brief = assemble_briefing(output, evidence, analysis, "evaluation-only", 1, bindings=record)
    if brief["quality"]["errors"]:
        raise ValueError("; ".join(brief["quality"]["errors"]))
    return {"rendered": output, "bindings": record, "fingerprint": _fingerprint(record)}


def _recorded(task, source, candidate):
    docs = source["documents"]
    evidence, analysis = copy.deepcopy(docs["evidence"]), copy.deepcopy(docs["analysis"])
    mode = candidate.get("mode", "bound")
    document = candidate["document"]
    if "synthetic_failure" in document:
        if document["synthetic_failure"] == "timeout":
            raise TimeoutError("Synthetic recorded timeout")
        raise ValueError("Synthetic recorded invalid output")
    if task.get("comparison") == "standard-deep":
        if candidate["label"] not in {"standard", "deep"} or document.get(
            "starting_input_sha256"
        ) != digest(docs):
            raise ValueError("Recorded stage pair lacks a matching frozen starting-input receipt")
        evidence, analysis = document["evidence"], document["analysis"]
        validate_analysis(analysis, evidence)
        state = document.get("state")
        if state is not None:
            prior = (
                (docs.get("research-audit") or {})
                .get("members", {})
                .get("prior-inventory.json", {})
                .get("document", {"status": "absent"})
            )
            validate_state(state, analysis, evidence, prior)
        return {
            "rendered": document,
            "state": state,
            "fingerprint": None,
            "evidence_sha256": digest(evidence),
            "analysis_sha256": digest(analysis),
        }
    original = None
    if task["kind"] == "counterfactual":
        original, old = render_candidate(document, evidence, analysis)
        changes = task.get("changes", [])
        targets = {c["observation_id"] for c in changes}
        if not targets or not targets <= {r["observation_id"] for r in old["bindings"]}:
            raise ValueError("Counterfactual targets must actually be referenced")
        observations = {o["id"]: o for o in evidence["observations"]}
        for change in changes:
            observations[change["observation_id"]][change["field"]] = change["value"]
    if mode == "legacy":
        brief = assemble_briefing(document, evidence, analysis, "evaluation-only", 1)
        if brief["quality"]["errors"]:
            raise ValueError("; ".join(brief["quality"]["errors"]))
        result = {"rendered": document, "fingerprint": None, "binding_mode": "legacy"}
    else:
        result = _bound(document, evidence, analysis)
    if original is not None:
        targets = {c["observation_id"] for c in task["changes"]}
        _, before_record = render_candidate(document, docs["evidence"], analysis)
        before = [r for r in before_record["bindings"] if r["observation_id"] not in targets]
        after = [r for r in result["bindings"]["bindings"] if r["observation_id"] not in targets]
        if before != after:
            raise ValueError("Counterfactual changed an unrelated quantity")
        result["counterfactual_targets"] = sorted(targets)
        result["semantic_direction_tested"] = False
    return {**result, "evidence_sha256": digest(evidence), "analysis_sha256": digest(analysis)}


def _live(task, source, label, mode, work, model_config):
    from ..comparisons import EMPTY
    from ..prior import load_prior
    from ..research_audit import write_audit
    from ..structured import research_structured

    docs = source["documents"]
    evidence, analysis = copy.deepcopy(docs["evidence"]), copy.deepcopy(docs["analysis"])
    config = {
        "analyst_model": "gpt-6-astra",
        "analyst_effort": "xhigh",
        "reviewer_model": "gpt-6-astra",
        "reviewer_effort": "high",
        "editor_model": "gpt-6.1-sol",
        "editor_effort": "medium",
        "timeout_seconds": 1200,
        **(model_config or {}),
        "run_dir": work,
        "run_id": "evaluation-only",
        "revision": 1,
    }
    if task.get("comparison") == "standard-deep":
        members = (docs.get("research-audit") or {}).get("members", {})
        prior = copy.deepcopy(
            members.get("prior-inventory.json", {}).get(
                "document", load_prior(None, evidence["market_date"], None)
            )
        )
        config.update(
            prior=prior,
            comparison_input=copy.deepcopy(
                members.get("comparison-input.json", {}).get("document", EMPTY)
            ),
            research_depth=label,
        )
        # Direct prior bytes are frozen from baseline, not re-read from the mutable input root.
        for name, item in source["files"].items():
            if name.startswith("prior-inputs/"):
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(item["raw"].encode("utf-8"))
        session = {
            "market_date": evidence["market_date"],
            "scheduled_close": evidence["scheduled_close"],
        }
        evidence, analysis, members = research_structured(session, datetime.now(UTC), config)
        write_atomic(work / "evidence.json", evidence)
        write_atomic(work / "analysis.json", analysis)
        write_audit(work, members)
    else:
        for name, item in source["files"].items():
            if name in {"briefing.json", "numeric-bindings.json", "review.json"}:
                continue
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item["raw"].encode("utf-8"))
    if mode == "legacy":
        prompt = (
            files("market_briefing")
            .joinpath("resources/prompts/evaluation-legacy-editor.zh-CN.md")
            .read_text(encoding="utf-8")
        )
        output = execute_stage(
            prompt
            + "\nFROZEN_INPUT_JSON\n"
            + json.dumps({"evidence": evidence, "analysis": analysis}, ensure_ascii=False),
            schema_path("editor"),
            work / "legacy.candidate.json",
            config["editor_model"],
            config["timeout_seconds"],
            work,
            command_prefix=config.get("command_prefix"),
            reasoning_effort=config["editor_effort"],
        )
        brief = assemble_briefing(output, evidence, analysis, "evaluation-only", 1)
        record = None
    else:
        brief = edit(analysis, evidence, config)
        record = json.loads((work / "numeric-bindings.json").read_text(encoding="utf-8"))
    if brief["quality"]["errors"]:
        raise ValueError("; ".join(brief["quality"]["errors"]))
    state = None
    if (work / "research-state.json").exists():
        state = json.loads((work / "research-state.json").read_text(encoding="utf-8"))
    return {
        "rendered": {"headline": brief["headline"], "paragraphs": brief["paragraphs"]},
        "bindings": record,
        "fingerprint": _fingerprint(record),
        "state": state,
        "evidence_sha256": digest(evidence),
        "analysis_sha256": digest(analysis),
    }


def evaluate(
    tasks: dict, out_dir: Path, *, live: bool = False, model_config: dict | None = None
) -> dict:
    model_config = {**DEFAULT_SETTINGS, **(model_config or {})}
    out = assert_external_path(out_dir)
    for source in tasks["frozen"].values():
        if out.is_relative_to(Path(source["root"]).resolve()):
            raise ValueError("Evaluation output cannot modify input revision")
    out.mkdir(parents=True, exist_ok=False)
    write_atomic(out / "evaluation-only.json", {"evaluation_only": True})
    write_atomic(out / "inputs.json", tasks)
    resource_root = Path(str(files("market_briefing")))
    tree = {
        p.relative_to(resource_root).as_posix(): p.read_bytes().hex()
        for p in resource_root.rglob("*")
        if p.is_file() and p.suffix in {".py", ".json", ".md"}
    }
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=resource_root, capture_output=True, text=True, timeout=5
    )
    manifest = {
        "schema_version": "market.research-evaluation.v1",
        "evaluation_only": True,
        "live": live,
        "started_at": datetime.now(UTC).isoformat(),
        "source_tasks_sha256": tasks["source_sha256"],
        "code_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "source_tree_digest": digest(tree),
        "resource_digest": digest({k: v for k, v in tree.items() if k.startswith("resources/")}),
        "requested_settings": {
            k: v
            for k, v in (model_config or {}).items()
            if k.endswith(("_model", "_effort")) or k == "timeout_seconds"
        },
    }
    write_atomic(out / "manifest.json", manifest)
    attempts = []
    for task in tasks["source"]["tasks"]:
        source = tasks["frozen"][task["id"]]
        candidates = source["candidates"]
        if live and task["kind"] == "paired":
            choices = (
                [("standard", "bound"), ("deep", "bound")]
                if task.get("comparison") == "standard-deep"
                else [("bound", "bound"), ("legacy", "legacy")]
            )
        elif live and task["kind"] == "repeat":
            choices = [("bound", "bound")]
        else:
            if not candidates and source["documents"].get("numeric-bindings"):
                candidates = [
                    {
                        "label": "frozen",
                        "mode": "bound",
                        "document": source["documents"]["numeric-bindings"]["candidate"],
                    }
                ]
            choices = [(c["label"], c.get("mode", "bound")) for c in candidates]
        if task["kind"] == "paired" and len(choices) != 2:
            raise ValueError("Paired experiment requires exactly two candidates/modes")
        if task.get("comparison") == "bound-legacy" and {mode for _, mode in choices} != {
            "bound",
            "legacy",
        }:
            raise ValueError("Bound/legacy comparison requires both modes")
        if not choices:
            raise ValueError("Evaluation needs recorded candidates or explicit live execution")
        repeats = task.get("repeats", 1)
        for repetition in range(repeats):
            for index, (label, mode) in enumerate(choices):
                row = {
                    "task_id": task["id"],
                    "kind": task["kind"],
                    "label": label,
                    "mode": mode,
                    "repetition": repetition,
                    "status": "failed",
                    "fingerprint": None,
                    "expected_error": task.get("expected_error"),
                    "starting_input_sha256": digest(source["documents"]),
                }
                started = time.monotonic()
                try:
                    if live and task["kind"] in {"repeat", "paired"}:
                        work = out / "stages" / f"{len(attempts) + 1:05d}"
                        work.mkdir(parents=True)
                        write_atomic(work / "evaluation-only.json", {"evaluation_only": True})
                        result = _live(task, source, label, mode, work, model_config)
                    else:
                        result = _recorded(task, source, candidates[index])
                    row.update(result, status="succeeded")
                except (
                    ValueError,
                    RuntimeError,
                    OSError,
                    TimeoutError,
                    KeyError,
                    TypeError,
                ) as exc:
                    row.update(
                        error_type=type(exc).__name__,
                        error=str(exc),
                        expected_failure_matched=type(exc).__name__ == task.get("expected_error"),
                    )
                row["duration_seconds"] = time.monotonic() - started
                attempts.append(row)
                write_atomic(out / "attempts" / f"{len(attempts):05d}.json", row)
    metrics = summarize(attempts)
    write_atomic(out / "attempts.json", {"attempts": attempts})
    write_atomic(out / "metrics.json", metrics)
    text = f"# Frozen research evaluation\n\nSuccessful attempts: {metrics['success']['n']}/{metrics['success']['N']}\n\nRepeat numeric consistency: {metrics['repeat_consistency']['n']}/{metrics['repeat_consistency']['N']}\n\nManual source correctness, relevance, explanation and readability: N/A (unlabeled).\n\nSee metrics.json for failures, unequal final evidence and unassessable state comparisons. These are descriptive software results, not forecast accuracy or source approval.\n"
    with (out / "metrics.md").open("x", encoding="utf-8") as stream:
        stream.write(text)
    return {"manifest": manifest, "metrics": metrics, "out_dir": str(out)}
