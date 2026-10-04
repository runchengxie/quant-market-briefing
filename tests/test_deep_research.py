import json
import sys
from datetime import UTC, datetime

import pytest

from market_briefing.cli import parser


def test_explicit_stage_defaults():
    args = parser().parse_args(["research"])
    assert (args.analyst_model, args.analyst_effort) == ("gpt-6-astra", "xhigh")
    assert (args.reviewer_model, args.reviewer_effort) == ("gpt-6-astra", "high")
    assert (args.editor_model, args.editor_effort) == ("gpt-6.1-sol", "medium")
    assert args.research_depth == "deep"


def test_two_research_rounds_are_retained(tmp_path, evidence, analysis, monkeypatch):
    from market_briefing import research as module

    result = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    calls = []

    def stage(prompt, schema, output, model, timeout, cwd, **kwargs):
        calls.append(
            (output.name, model, kwargs["reasoning_effort"], kwargs["require_search"], prompt)
        )
        output.write_text(json.dumps(result), encoding="utf-8")
        return result

    monkeypatch.setattr(module, "execute_stage", stage)
    session = {
        "market_date": evidence["market_date"],
        "scheduled_close": evidence["scheduled_close"],
    }
    config = {
        "run_dir": tmp_path,
        "analyst_model": "gpt-6-astra",
        "analyst_effort": "xhigh",
        "reviewer_model": "gpt-6-astra",
        "reviewer_effort": "high",
        "research_depth": "deep",
    }
    returned, final = module.research(session, datetime(2026, 10, 3, 8, tzinfo=UTC), config)
    assert [c[:4] for c in calls] == [
        ("research.candidate.json", "gpt-6-astra", "xhigh", True),
        ("challenge.candidate.json", "gpt-6-astra", "high", True),
    ]
    assert "反方" in calls[1][4] and "参考初稿" in calls[1][4]
    assert (tmp_path / "research.initial.json").exists()
    assert returned["sources"] == evidence["sources"] and final == analysis


def test_invalid_effort_fails_before_process(tmp_path):
    from market_briefing.codex import execute_stage
    from market_briefing.contracts import schema_path

    with pytest.raises(ValueError, match="reasoning_effort"):
        execute_stage(
            "",
            schema_path("editor"),
            tmp_path / "out.json",
            "gpt-6-astra",
            5,
            tmp_path,
            reasoning_effort="invalid",
            command_prefix=["missing"],
        )


def test_explicit_options_reach_process_and_metadata(tmp_path, editor_output):
    from market_briefing.codex import execute_stage
    from market_briefing.contracts import schema_path

    script = tmp_path / "fake.py"
    script.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        "assert sys.argv[sys.argv.index('--model')+1]=='gpt-6-astra'\n"
        "assert 'model_reasoning_effort=\"xhigh\"' in sys.argv\n"
        "sys.stdin.buffer.read()\n"
        f"Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({json.dumps(editor_output)!r},encoding='utf-8')\n",
        encoding="utf-8",
    )
    result = execute_stage(
        "研究",
        schema_path("editor"),
        tmp_path / "out.json",
        "gpt-6-astra",
        5,
        tmp_path,
        command_prefix=[sys.executable, str(script)],
        reasoning_effort="xhigh",
    )
    assert result == editor_output
    metadata = json.loads(next(tmp_path.glob("out.*.invocation.json")).read_text())
    assert metadata["requested_model"] == "gpt-6-astra"
    assert metadata["requested_reasoning_effort"] == "xhigh"
    assert metadata["codex_version"] == "test-double"
    assert len(metadata["prompt_sha256"]) == 64
    assert (
        json.loads(next(tmp_path.glob("out.*.completion.json")).read_text())["elapsed_seconds"] >= 0
    )
