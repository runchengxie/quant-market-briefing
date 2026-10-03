import copy
import json
import sys
from datetime import UTC, datetime
from importlib.resources import files

import pytest

from market_briefing.cli import main
from market_briefing.codex import execute_stage
from market_briefing.contracts import schema_path


def test_original_framework_is_packaged():
    prompt = files("market_briefing").joinpath("resources/prompts/research-framework.zh-CN.md")
    assert "近期内部人交易" in prompt.read_text(encoding="utf-8")


@pytest.mark.parametrize("search_event", [True, False])
def test_web_research_and_editor(tmp_path, evidence, analysis, editor_output, search_event):
    payloads = tmp_path / "payloads.json"
    payloads.write_text(
        json.dumps(
            {
                "research": {
                    "sources": evidence["sources"],
                    "observations": evidence["observations"],
                    "analysis": analysis,
                },
                "editor": editor_output,
            }
        ),
        encoding="utf-8",
    )
    script = tmp_path / "fake.py"
    script.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        "args=sys.argv\nprompt=sys.stdin.buffer.read().decode('utf-8')\n"
        "schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text())\n"
        "research='analysis' in schema['properties']\n"
        "assert ('web_search=\"live\"' if research else 'web_search=\"disabled\"') in args\n"
        "if research: assert '近期内部人交易' in prompt\n"
        f"data=json.loads(Path({str(payloads)!r}).read_text(encoding='utf-8'))\n"
        f"if research and {search_event!r}: print(json.dumps({{'type':'item.completed','item':{{'type':'web_search'}}}}))\n"
        "Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(data['research' if research else 'editor']),encoding='utf-8')\n",
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    result = main(
        ["research", "--date", "2026-10-02", "--data-root", str(root)],
        command_prefix=[sys.executable, str(script)],
        now=datetime(2026, 10, 3, 8, tzinfo=UTC),
    )
    run = root / "2026-10-02/r0001"
    if search_event:
        assert result == 0
        brief = json.loads((run / "briefing.json").read_text(encoding="utf-8"))
        assert brief["status"] == "validated_draft"
        assert brief["quality"]["source_audit_passed"] is False
        assert (run / "research.candidate.json").exists()
        assert json.loads((run / "run.json").read_text())["input_mode"] == "web_research"
    else:
        assert result == 2
        assert not (run / "briefing.json").exists()
        assert not (run / "evidence.json").exists()


def test_collected_sources_do_not_grant_publication_approval(tmp_path, evidence, analysis):
    from market_briefing.research import assemble_research

    result = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    context = {
        key: value for key, value in evidence.items() if key not in {"sources", "observations"}
    }
    assembled, returned = assemble_research(result, context)
    assert returned == analysis
    assert assembled["market_date"] == context["market_date"]
    broken = copy.deepcopy(result)
    broken["sources"][0]["published_at"] = "2026-10-04T10:00:00Z"
    with pytest.raises(ValueError, match="after evidence cutoff"):
        assemble_research(broken, context)


def test_invalid_search_mode_never_starts_process(tmp_path):
    with pytest.raises(ValueError, match="web_search"):
        execute_stage(
            "",
            schema_path("editor"),
            tmp_path / "output.json",
            None,
            5,
            tmp_path,
            command_prefix=["missing"],
            web_search="typo",
        )


@pytest.mark.parametrize("unit", ["percent", "basis_points"])
def test_financial_units_are_explicit(evidence, unit):
    from market_briefing.contracts import validate_document

    evidence["observations"][0]["unit"] = unit
    validate_document(evidence, "evidence")


def test_research_schema_matches_existing_contracts():
    research_schema = json.loads(schema_path("research").read_text())
    evidence_schema = json.loads(schema_path("evidence").read_text())
    analysis_schema = json.loads(schema_path("analysis").read_text())
    analysis_schema.pop("$schema")
    assert research_schema["properties"]["analysis"] == analysis_schema
    for name in ("sources", "observations"):
        assert research_schema["properties"][name] == evidence_schema["properties"][name]


@pytest.mark.parametrize(
    "now,date",
    [
        (datetime(2026, 10, 3, 8, tzinfo=UTC), "2026-10-02"),
        (datetime(2026, 10, 2, 18, tzinfo=UTC), "2026-10-01"),
        (datetime(2026, 11, 27, 19, tzinfo=UTC), "2026-11-27"),
    ],
)
def test_latest_completed_session(now, date):
    from market_briefing.calendar import select_session

    assert select_session(now, "latest")["market_date"] == date
