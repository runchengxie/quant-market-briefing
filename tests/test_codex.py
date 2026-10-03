import json
import sys

import pytest

from market_briefing.codex import execute_stage
from market_briefing.contracts import schema_path


@pytest.mark.parametrize("mode", ["ok", "exit", "timeout", "badjson", "missing", "badshape"])
def test_stage_process_integrity(tmp_path, mode, editor_output):
    script = tmp_path / "fake.py"
    script.write_text(
        "import sys,json,time\n"
        "from pathlib import Path\n"
        f"mode={mode!r}\n"
        "output=Path(sys.argv[sys.argv.index('--output-last-message')+1])\n"
        "prompt=sys.stdin.buffer.read().decode('utf-8')\n"
        "assert '研究' in prompt\n"
        "if mode=='timeout': time.sleep(10)\n"
        "if mode=='exit': output.write_text('{}'); sys.exit(2)\n"
        "if mode!='missing': output.write_text("
        + repr(
            "broken"
            if mode == "badjson"
            else "{}"
            if mode == "badshape"
            else json.dumps(editor_output)
        )
        + ",encoding='utf-8')\n",
        encoding="utf-8",
    )
    output = tmp_path / "result.json"
    kwargs = dict(
        prompt="研究材料",
        schema=schema_path("editor"),
        output=output,
        model=None,
        timeout_seconds=0.2 if mode == "timeout" else 5,
        cwd=tmp_path,
        command_prefix=[sys.executable, str(script)],
    )
    if mode == "ok":
        assert execute_stage(**kwargs) == editor_output
        assert output.exists()
    else:
        with pytest.raises((ValueError, RuntimeError, TimeoutError)):
            execute_stage(**kwargs)
        assert not output.exists()
        assert list(tmp_path.glob("result.*attempt-1.events.jsonl"))


def test_failed_retries_preserve_prior_logs(tmp_path):
    script = tmp_path / "exit.py"
    script.write_text('import sys\nsys.stdin.buffer.read()\nprint("attempt")\nsys.exit(2)\n')
    for _ in range(2):
        with pytest.raises(RuntimeError):
            execute_stage(
                "prompt",
                schema_path("editor"),
                tmp_path / "result.json",
                None,
                5,
                tmp_path,
                command_prefix=[sys.executable, str(script)],
            )
    assert len(list(tmp_path.glob("result.*attempt-1.events.jsonl"))) == 2


def test_refuse_overwrite(tmp_path):
    output = tmp_path / "result.json"
    output.write_text("existing")
    with pytest.raises(FileExistsError):
        execute_stage("prompt", schema_path("editor"), output, None, 5, tmp_path)
    assert output.read_text() == "existing"
