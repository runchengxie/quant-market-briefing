import copy
import json
import sys
from datetime import UTC, datetime

import pytest


def candidate(evidence, analysis):
    return {
        **{
            key: copy.deepcopy(evidence[key])
            for key in ["sources", "observations", "events", "scheduled_events", "missing_inputs"]
        },
        "comparison_requests": [{"start_id": "o1", "end_id": "o2", "method": "return"}],
        "analysis": copy.deepcopy(analysis),
    }


def fake_command(tmp_path, payload, search=True, failure=None):
    data = tmp_path / "payload.json"
    data.write_text(json.dumps(payload), encoding="utf-8")
    script = tmp_path / "fake.py"
    script.write_text(
        "import sys,json,time\nfrom pathlib import Path\nargs=sys.argv\nprompt=sys.stdin.buffer.read().decode('utf-8')\n"
        f"failure={failure!r}\n"
        "if failure=='timeout': time.sleep(2)\n"
        "if failure=='exit': sys.exit(1)\n"
        "schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text())\n"
        "research='analysis' in schema['properties']\n"
        "assert ('web_search=\"live\"' if research else 'web_search=\"disabled\"') in args\n"
        f"payload=json.loads(Path({str(data)!r}).read_text(encoding='utf-8'))\n"
        f"if research and {search!r}: print(json.dumps({{'type':'item.completed','item':{{'type':'web_search'}}}}))\n"
        "out=payload['research' if research else 'editor'] if 'research' in payload else payload\n"
        "Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(out),encoding='utf-8')\n",
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


@pytest.mark.parametrize("depth,invocations", [("deep", 2), ("standard", 1)])
def test_live_weekly_research(tmp_path, weekly_evidence, weekly_analysis, depth, invocations):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.research import research_week

    now = datetime(2026, 10, 3, 8, tzinfo=UTC)
    payload = candidate(weekly_evidence, weekly_analysis)
    config = {
        "run_dir": tmp_path,
        "command_prefix": fake_command(tmp_path, payload),
        "research_depth": depth,
        "timeout_seconds": 5,
        "analyst_model": "gpt-6-astra",
        "analyst_effort": "xhigh",
        "reviewer_model": "gpt-6-astra",
        "reviewer_effort": "high",
    }
    evidence, analysis = research_week(select_week(now), now, config)
    assert evidence["comparisons"][0]["value"] == 5
    assert analysis["previous_view"]["status"] == "absent"
    assert len(list(tmp_path.glob("*.invocation.json"))) == invocations
    assert (tmp_path / "research.initial.json").is_file()
    assert (tmp_path / "event-groups.json").is_file()
    if depth == "deep":
        assert (tmp_path / "challenge.reconciliation.json").is_file()


@pytest.mark.parametrize("failure", ["no_search", "schema", "timeout", "exit"])
def test_failed_research_keeps_diagnostics(tmp_path, weekly_evidence, weekly_analysis, failure):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.research import research_week

    payload = candidate(weekly_evidence, weekly_analysis)
    if failure == "schema":
        payload["analysis"]["claims"][0]["evidence_ids"] = ["unknown"]
    now = datetime(2026, 10, 3, 8, tzinfo=UTC)
    config = {
        "run_dir": tmp_path,
        "timeout_seconds": 0.1 if failure == "timeout" else 5,
        "command_prefix": fake_command(tmp_path, payload, failure != "no_search", failure),
        "research_depth": "deep",
    }
    with pytest.raises((ValueError, RuntimeError, TimeoutError)):
        research_week(select_week(now), now, config)
    assert list(tmp_path.glob("*.events.jsonl"))
    assert not (tmp_path / "evidence.json").exists()


def test_changed_records_receive_fresh_ids(weekly_evidence, weekly_analysis):
    from market_briefing.weekly.research import reconcile_weekly_revision

    initial = candidate(weekly_evidence, weekly_analysis)
    revised = copy.deepcopy(initial)
    revised["sources"][0]["title"] = "Correction"
    reconciled, mapping = reconcile_weekly_revision(initial, revised)
    assert mapping["sources"]["s1"] != "s1"
    assert reconciled["observations"][0]["source_id"] == mapping["sources"]["s1"]
    assert reconciled["events"][0]["evidence_ids"][0] == mapping["observations"]["o2"]
    assert reconciled["analysis"]["claims"][0]["evidence_ids"] == [mapping["events"]["e1"]]
    assert initial["sources"][0]["title"] == "Synthetic official release"


def test_grouping_preserves_corrections(weekly_evidence):
    from market_briefing.weekly.research import group_events

    events = weekly_evidence["events"]
    events.append(
        {**events[0], "id": "e2", "event_at": "2026-10-02T15:00:00Z", "development": "Correction"}
    )
    assert [item["id"] for item in group_events(events)["macro.synthetic"]] == ["e1", "e2"]
