import json
import sys
from pathlib import Path

from market_briefing.cli import main


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
        "Path(target).write_bytes(Path(source).read_bytes())\n", encoding="utf-8")
    monkeypatch.setenv("MARKET_BRIEFING_TEST_COMMAND", json.dumps([sys.executable, str(fake)]))
    frozen = tmp_path / "evidence.json"
    frozen.write_text(json.dumps(evidence), encoding="utf-8")
    root = tmp_path / "runtime"
    args = ["run", "--date", "2026-10-02", "--evidence", str(frozen), "--data-root", str(root)]
    assert main(args) == 0
    first = root / "2026-10-02" / "r0001"
    brief = json.loads((first / "briefing.json").read_text(encoding="utf-8"))
    assert brief["status"] == "validated_draft"
    assert not (first / "bundle").exists()
    assert main(args) == 0
    assert (root / "2026-10-02" / "r0002" / "briefing.json").exists()
    assert main(["validate", "--run-dir", str(first)]) == 0


def test_bad_evidence_never_starts_model(tmp_path, evidence, monkeypatch):
    evidence["observations"][0]["unit"] = "unknown"
    frozen = tmp_path / "evidence.json"
    frozen.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setenv("MARKET_BRIEFING_TEST_COMMAND", '["nonexistent"]')
    assert main(["run", "--date", "2026-10-02", "--evidence", str(frozen),
                 "--data-root", str(tmp_path / "runtime")]) == 2
    assert not (tmp_path / "runtime").exists()
