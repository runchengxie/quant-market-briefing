import json
import sys

import pytest

from market_briefing.cli import main
from market_briefing.storage import assert_external_path


def test_help(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "bundle" in capsys.readouterr().out


def test_pipeline_with_fake_model(tmp_path, evidence, analysis, editor_output, monkeypatch, capsys):
    fake = tmp_path / "fake.py"
    analysis_file = tmp_path / "fake-analysis.json"
    editor_file = tmp_path / "fake-editor.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")
    editor_file.write_text(json.dumps(editor_output), encoding="utf-8")
    fake.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        "schema=sys.argv[sys.argv.index('--output-schema')+1]\n"
        "target=sys.argv[sys.argv.index('--output-last-message')+1]\n"
        "prompt=sys.stdin.buffer.read().decode('utf-8')\n"
        f"source={str(analysis_file)!r} if 'analysis.v1' in schema else {str(editor_file)!r}\n"
        "Path(target).write_bytes(Path(source).read_bytes())\n",
        encoding="utf-8",
    )
    command_prefix = [sys.executable, str(fake)]
    frozen = tmp_path / "evidence.json"
    frozen.write_text(json.dumps(evidence), encoding="utf-8")
    root = tmp_path / "runtime"
    args = ["run", "--date", "2026-10-02", "--evidence", str(frozen), "--data-root", str(root)]
    assert main(args, command_prefix=command_prefix) == 0
    first = root / "2026-10-02" / "r0001"
    brief = json.loads((first / "briefing.json").read_text(encoding="utf-8"))
    assert brief["status"] == "validated_draft"
    assert not (first / "bundle").exists()
    assert main(args, command_prefix=command_prefix) == 0
    assert (root / "2026-10-02" / "r0002" / "briefing.json").exists()
    assert main(["validate", "--run-dir", str(first)]) == 0


def test_bad_evidence_never_starts_model(tmp_path, evidence, monkeypatch):
    evidence["observations"][0]["unit"] = "unknown"
    frozen = tmp_path / "evidence.json"
    frozen.write_text(json.dumps(evidence), encoding="utf-8")
    assert (
        main(
            [
                "run",
                "--date",
                "2026-10-02",
                "--evidence",
                str(frozen),
                "--data-root",
                str(tmp_path / "runtime"),
            ],
            command_prefix=["nonexistent"],
        )
        == 2
    )
    assert not (tmp_path / "runtime").exists()


def test_runtime_destination_cannot_be_under_git_source(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: somewhere")
    with pytest.raises(ValueError):
        assert_external_path(repo / "reports")
    assert not (repo / "reports").exists()


def test_editor_inherits_recorded_model_and_rejects_changed_resources(
    tmp_path, evidence, analysis, monkeypatch
):
    from market_briefing import cli
    from market_briefing.review import file_hash
    from market_briefing.storage import write_atomic

    run = tmp_path / "runtime" / "2026-10-02" / "r0001"
    write_atomic(run / "evidence.json", evidence)
    write_atomic(run / "analysis.json", analysis)
    metadata = {
        "revision": 1,
        "run_id": "us-2026-10-02-r0001",
        "evidence_sha256": file_hash(run / "evidence.json"),
        "editor_model": "saved-model",
        "resource_hashes": cli.resource_hashes(),
    }
    write_atomic(run / "run.json", metadata)
    seen = []
    monkeypatch.setattr(cli, "_finish_editor", lambda e, a, c: seen.append(c["editor_model"]) or 0)
    assert main(["edit", "--run-dir", str(run)]) == 0
    assert seen == ["saved-model"]
    assert main(["edit", "--run-dir", str(run), "--editor-model", "different"]) == 2
    monkeypatch.setattr(cli, "resource_hashes", lambda: {"changed": "hash"})
    assert main(["edit", "--run-dir", str(run)]) == 2
    assert seen == ["saved-model"]
