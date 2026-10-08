import json
from datetime import UTC, datetime

import pytest

from market_briefing.cli import main

from .test_research import candidate, fake_command


def test_editor_output_and_source_audit(weekly_evidence, weekly_analysis, weekly_editor_output):
    from market_briefing.weekly.editor import assemble_weekly_briefing

    brief = assemble_weekly_briefing(
        weekly_editor_output, weekly_evidence, weekly_analysis, "us-weekly-2026-09-28-r0001", 1
    )
    assert brief["status"] == "validated_draft"
    assert brief["quality"]["source_audit_passed"] is False
    assert brief["quality"]["warnings"]
    assert "合成资料\n" in brief["brief_text"]
    assert "缺少真实资料" in brief["missing_inputs"]


@pytest.mark.parametrize("mode", ["number", "unknown", "order", "metadata", "estimate", "sources"])
def test_weekly_draft_rejects_invention(
    weekly_evidence, weekly_analysis, weekly_editor_output, mode
):
    from market_briefing.weekly.editor import assemble_weekly_briefing
    from market_briefing.weekly.validate import validate_weekly_draft

    if mode == "number":
        weekly_editor_output["sections"][0]["text"] += "上涨999%。"
    if mode == "unknown":
        weekly_editor_output["sections"][0]["claim_ids"] = ["unknown"]
    if mode == "order":
        weekly_editor_output["sections"].reverse()
    if mode == "estimate":
        weekly_analysis["claims"][0]["temporal_type"] = "estimate"
    if mode in {"order", "estimate"}:
        with pytest.raises(ValueError):
            assemble_weekly_briefing(
                weekly_editor_output, weekly_evidence, weekly_analysis, "run", 1
            )
        return
    brief = assemble_weekly_briefing(
        weekly_editor_output, weekly_evidence, weekly_analysis, "run", 1
    )
    if mode == "metadata":
        brief["week_start"] = "2026-10-05"
    if mode == "sources":
        brief["sources"][0]["title"] = "changed"
    quality = validate_weekly_draft(weekly_evidence, weekly_analysis, brief)
    assert quality["errors"]


def test_known_schedule_date_and_headings(weekly_evidence, weekly_analysis, weekly_editor_output):
    from market_briefing.weekly.editor import assemble_weekly_briefing

    weekly_editor_output["sections"][4]["text"] = "- 合成日程预定于10月6日公布，实际结果仍未知。"
    brief = assemble_weekly_briefing(
        weekly_editor_output, weekly_evidence, weekly_analysis, "run", 1
    )
    assert brief["quality"]["errors"] == []


def run_week(tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output, **kwargs):
    payload = {
        "research": candidate(weekly_evidence, weekly_analysis),
        "editor": weekly_editor_output,
    }
    command = fake_command(tmp_path, payload)
    root = tmp_path / "runtime"
    args = ["weekly-research", "--week-start", "2026-09-28", "--data-root", str(root)]
    assert main(args, command_prefix=command, now=datetime(2026, 10, 3, 8, tzinfo=UTC)) == 0
    return root, root / "weekly/2026-09-28/r0001", command, args


def test_weekly_cli_and_daily_compatibility(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
):
    root, run, command, args = run_week(
        tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
    )
    assert (run / "briefing.txt").is_file()
    assert (run / "validation.json").is_file()
    assert json.loads((run / "run.json").read_text())["product"] == "weekly"
    assert main(["weekly-validate", "--run-dir", str(run)]) == 0
    assert main(["weekly-edit", "--run-dir", str(run)], command_prefix=command) == 2
    assert main(args, command_prefix=command, now=datetime(2026, 10, 3, 8, tzinfo=UTC)) == 0
    assert (root / "weekly/2026-09-28/r0002/briefing.json").is_file()


@pytest.mark.parametrize(
    "mutation", ["evidence", "analysis", "context", "resources", "identity", "model", "effort"]
)
def test_resumed_edit_rejects_changes(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output, mutation
):
    root, run, command, args = run_week(
        tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
    )
    # A completed final output blocks edits regardless; simulate a failed pre-output editor.
    for name in ["briefing.json", "briefing.txt", "validation.json", "editor.candidate.json"]:
        (run / name).unlink()
    args = ["weekly-edit", "--run-dir", str(run)]
    if mutation in {"evidence", "analysis", "context"}:
        filename = "weekly-context.json" if mutation == "context" else mutation + ".json"
        with (run / filename).open("a") as stream:
            stream.write(" ")
    else:
        metadata = json.loads((run / "run.json").read_text())
        if mutation == "resources":
            metadata["resource_hashes"] = {}
        if mutation == "identity":
            metadata["run_id"] = "wrong"
        if mutation == "model":
            args += ["--editor-model", "another"]
        if mutation == "effort":
            args += ["--editor-effort", "high"]
        (run / "run.json").write_text(json.dumps(metadata))
    before = len(list(run.glob("*.invocation.json")))
    assert main(args, command_prefix=command) == 2
    assert len(list(run.glob("*.invocation.json"))) == before


def test_workspace_config_and_invalid_inputs(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
):
    config = tmp_path / "workspace.toml"
    config.write_text(f'data_root = "{tmp_path.as_posix()}"')
    command = fake_command(
        tmp_path,
        {"research": candidate(weekly_evidence, weekly_analysis), "editor": weekly_editor_output},
    )
    now = datetime(2026, 10, 3, 8, tzinfo=UTC)
    assert (
        main(
            ["weekly-research", "--workspace-config", str(config)], command_prefix=command, now=now
        )
        == 0
    )
    assert (tmp_path / "quant-market-briefing/weekly/2026-09-28/r0001/briefing.json").exists()
    assert (
        main(
            [
                "weekly-research",
                "--data-root",
                str(tmp_path / "invalid"),
                "--week-start",
                "2026-10-05",
            ],
            command_prefix=command,
            now=now,
        )
        == 2
    )
    assert not (tmp_path / "invalid").exists()


def test_failure_retains_diagnostics(tmp_path, weekly_evidence, weekly_analysis):
    command = fake_command(tmp_path, candidate(weekly_evidence, weekly_analysis), search=False)
    root = tmp_path / "runtime"
    assert (
        main(
            ["weekly-research", "--data-root", str(root)],
            command_prefix=command,
            now=datetime(2026, 10, 3, 8, tzinfo=UTC),
        )
        == 2
    )
    run = root / "weekly/2026-09-28/r0001"
    assert (run / "failure.json").exists()
    assert not (run / "briefing.json").exists()
