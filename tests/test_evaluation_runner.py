import json

import pytest

from market_briefing.editor import assemble_briefing
from market_briefing.evaluation.runner import evaluate
from market_briefing.evaluation.tasks import load_tasks
from market_briefing.numeric_bindings import render_candidate


def task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output, kind="repeat"):
    run = tmp_path / "source"
    run.mkdir()
    brief = assemble_briefing(editor_output, evidence, analysis, "legacy", 1)
    for name, doc in [("evidence", evidence), ("analysis", analysis), ("briefing", brief)]:
        (run / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(bound_editor_output), encoding="utf-8")
    path = tmp_path / "tasks.json"
    task = {
        "id": "task",
        "kind": kind,
        "run_dir": str(run),
        "candidates": [{"label": "bound", "path": str(candidate)}],
    }
    path.write_text(
        json.dumps({"schema_version": "market.evaluation-tasks.v1", "tasks": [task]}),
        encoding="utf-8",
    )
    return path


def test_offline_repeat_never_calls_model(
    tmp_path, evidence, analysis, editor_output, bound_editor_output, monkeypatch
):
    path = task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output)
    monkeypatch.setattr(
        "market_briefing.codex.execute_stage", lambda *a, **kw: pytest.fail("paid stage")
    )
    result = evaluate(load_tasks(path), tmp_path / "evaluation")
    assert result["metrics"]["success"] == {"n": 1, "N": 1}
    assert not (tmp_path / "evaluation/briefing.json").exists()
    with pytest.raises(FileExistsError):
        evaluate(load_tasks(path), tmp_path / "evaluation")


def test_counterfactual_follows_only_target(
    tmp_path, evidence, analysis, editor_output, bound_editor_output
):
    path = task_file(
        tmp_path, evidence, analysis, editor_output, bound_editor_output, "counterfactual"
    )
    payload = json.loads(path.read_text())
    payload["tasks"][0]["changes"] = [{"observation_id": "e1", "field": "value", "value": -2.5}]
    path.write_text(json.dumps(payload))
    result = evaluate(load_tasks(path), tmp_path / "evaluation")
    assert result["metrics"]["success"]["n"] == 1
    attempts = json.loads((tmp_path / "evaluation/attempts.json").read_text(encoding="utf-8"))[
        "attempts"
    ]
    assert "负2.5" in attempts[0]["rendered"]["paragraphs"][0]["text"]
    assert evidence["observations"][0]["value"] == 0.73


def test_duplicate_tasks_rejected(tmp_path, evidence, analysis, editor_output, bound_editor_output):
    path = task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output)
    payload = json.loads(path.read_text())
    payload["tasks"] *= 2
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_tasks(path)


def test_production_binding_survives_legacy_evaluation(
    tmp_path, evidence, analysis, editor_output, bound_editor_output
):
    path = task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output, "paired")
    payload = json.loads(path.read_text())
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps(editor_output), encoding="utf-8")
    task = payload["tasks"][0]
    task["comparison"] = "bound-legacy"
    task["candidates"][0]["mode"] = "bound"
    task["candidates"].append({"label": "legacy", "path": str(legacy), "mode": "legacy"})
    path.write_text(json.dumps(payload))
    result = evaluate(load_tasks(path), tmp_path / "evaluation")
    assert result["metrics"]["success"] == {"n": 2, "N": 2}
    with pytest.raises(ValueError):
        render_candidate(editor_output, evidence, analysis)


def test_cli_freezes_inputs_and_failure_denominators(
    tmp_path, evidence, analysis, editor_output, bound_editor_output
):
    from market_briefing.cli import main

    path = task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output, "failure")
    payload = json.loads(path.read_text())
    payload["tasks"][0]["expected_error"] = "TimeoutError"
    path.write_text(json.dumps(payload))
    (tmp_path / "candidate.json").write_text(json.dumps({"synthetic_failure": "timeout"}))
    frozen = load_tasks(path)
    (tmp_path / "candidate.json").write_text("{}")
    result = evaluate(frozen, tmp_path / "failure-eval")
    assert result["metrics"]["success"] == {"n": 0, "N": 1}
    assert result["metrics"]["expected_failure_matches"] == {"n": 1, "N": 1}
    assert main(["evaluate", "--tasks", str(path), "--out-dir", str(tmp_path / "cli-eval")]) == 0


def test_grade_source_key_is_separate(tmp_path):
    from market_briefing.evaluation.grading import export_grading

    rows = [
        {
            "task_id": "p",
            "kind": "paired",
            "label": label,
            "status": "succeeded",
            "rendered": {"headline": "合成", "paragraphs": [{"text": "候选正文"}]},
        }
        for label in ["secret-source-a", "secret-source-b"]
    ]
    export_grading(rows, tmp_path / "grades", 42)
    csv = (tmp_path / "grades/grades.csv").read_text(encoding="utf-8-sig")
    assert "secret-source" not in csv
    assert "secret-source-a" in (tmp_path / "grades/source-key.json").read_text()


def test_explicit_live_uses_fake_process_and_cannot_bundle(
    tmp_path, evidence, analysis, editor_output, bound_editor_output
):
    import sys

    from market_briefing.publication import build_bundle

    path = task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output)
    script = tmp_path / "fake.py"
    script.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        "args=sys.argv\nprompt=sys.stdin.buffer.read().decode('utf-8')\n"
        "assert 'web_search=\"disabled\"' in args\n"
        f"Path(args[args.index('--output-last-message')+1]).write_text({json.dumps(bound_editor_output)!r},encoding='utf-8')\n",
        encoding="utf-8",
    )
    result = evaluate(
        load_tasks(path),
        tmp_path / "live",
        live=True,
        model_config={"command_prefix": [sys.executable, str(script)]},
    )
    assert result["metrics"]["success"] == {"n": 1, "N": 1}
    assert result["manifest"]["requested_settings"]["editor_model"] == "gpt-6.1-sol"
    with pytest.raises(ValueError, match="Evaluation"):
        build_bundle(
            tmp_path / "live/stages/00001", tmp_path / "missing-review.json", "a" * 40, "internal"
        )


def test_recorded_stage_pair_requires_starting_receipt(
    tmp_path, evidence, analysis, editor_output, bound_editor_output
):
    from market_briefing.numeric_bindings import digest

    path = task_file(tmp_path, evidence, analysis, editor_output, bound_editor_output, "paired")
    payload = json.loads(path.read_text())
    task = payload["tasks"][0]
    task["comparison"] = "standard-deep"
    baseline = {
        k: json.loads((tmp_path / "source" / f"{k}.json").read_text(encoding="utf-8"))
        for k in ["evidence", "analysis", "briefing"]
    }
    task["candidates"] = []
    for label in ["standard", "deep"]:
        candidate = tmp_path / f"{label}.json"
        record = {"evidence": evidence, "analysis": analysis, "starting_input_sha256": "wrong"}
        candidate.write_text(json.dumps(record), encoding="utf-8")
        task["candidates"].append({"label": label, "path": str(candidate), "mode": "research"})
    path.write_text(json.dumps(payload))
    result = evaluate(load_tasks(path), tmp_path / "bad-pair")
    assert result["metrics"]["success"] == {"n": 0, "N": 2}
    for label in ["standard", "deep"]:
        candidate = tmp_path / f"{label}.json"
        record = json.loads(candidate.read_text())
        record["starting_input_sha256"] = digest(baseline)
        candidate.write_text(json.dumps(record))
    result = evaluate(load_tasks(path), tmp_path / "good-pair")
    assert result["metrics"]["success"] == {"n": 2, "N": 2}
