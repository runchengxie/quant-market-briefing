import copy
import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["codex", "--version"]),
        subprocess.TimeoutExpired(["codex", "--version"], 10),
    ],
)
def test_version_probe_failure_is_clean_and_normalized(tmp_path, monkeypatch, error):
    from market_briefing import codex
    from market_briefing.contracts import schema_path

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(codex.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="version probe"):
        codex.execute_stage(
            "", schema_path("editor"), tmp_path / "out.json", "gpt-6-astra", 5, tmp_path
        )
    assert not list(tmp_path.glob(".*.schema.json"))
    assert not (tmp_path / "out.json").exists()


def test_completion_write_failure_does_not_commit_result(tmp_path, editor_output, monkeypatch):
    from market_briefing import codex
    from market_briefing.contracts import schema_path

    script = tmp_path / "fake.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\nsys.stdin.buffer.read()\n"
        f"Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({json.dumps(editor_output)!r},encoding='utf-8')\n",
        encoding="utf-8",
    )
    original = codex.write_atomic

    def fail_completion(path, value):
        if path.name.endswith(".completion.json"):
            raise OSError("completion failed")
        return original(path, value)

    monkeypatch.setattr(codex, "write_atomic", fail_completion)
    with pytest.raises(OSError, match="completion failed"):
        codex.execute_stage(
            "",
            schema_path("editor"),
            tmp_path / "out.json",
            "gpt-6-astra",
            5,
            tmp_path,
            command_prefix=[sys.executable, str(script)],
        )
    assert not (tmp_path / "out.json").exists()
    assert not list(tmp_path.glob(".*.schema.json"))


def test_challenge_cannot_reassign_existing_observation_id(
    tmp_path, evidence, analysis, monkeypatch
):
    from market_briefing import research as module

    original = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    changed = copy.deepcopy(original)
    changed["observations"][0]["value"] = 999
    count = 0

    def stage(prompt, schema, output, *args, **kwargs):
        nonlocal count
        count += 1
        result = original if count == 1 else changed
        output.write_text(json.dumps(result), encoding="utf-8")
        return result

    monkeypatch.setattr(module, "execute_stage", stage)
    returned, _ = module.research(
        {"market_date": evidence["market_date"], "scheduled_close": evidence["scheduled_close"]},
        datetime(2026, 10, 3, 8, tzinfo=UTC),
        {"run_dir": tmp_path, "research_depth": "deep"},
    )
    assert returned["observations"][0]["id"] != original["observations"][0]["id"]
    assert returned["observations"][0]["value"] == 999
    assert (tmp_path / "challenge.reconciliation.json").exists()


def test_revision_rejects_source_reassignment(evidence, analysis):
    from market_briefing.research import validate_revision

    initial = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    revised = copy.deepcopy(initial)
    revised["sources"][0]["title"] = "Different source"
    with pytest.raises(ValueError, match="reassign sources"):
        validate_revision(initial, revised)


def test_revision_allows_correction_with_new_identifier(evidence, analysis):
    from market_briefing.research import validate_revision

    initial = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    revised = copy.deepcopy(initial)
    correction = copy.deepcopy(revised["observations"][0])
    correction["id"] = "obs_correction"
    correction["value"] = 999
    revised["observations"].append(correction)
    validate_revision(initial, revised)


def test_reconciliation_preserves_content_and_updates_references(evidence, analysis):
    from market_briefing.research import reconcile_revision, validate_revision

    initial = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    revised = copy.deepcopy(initial)
    source_id = revised["sources"][0]["id"]
    observation_id = revised["observations"][0]["id"]
    revised["sources"][0]["title"] = "Revised title"
    revised["observations"][0]["value"] = 999
    before = copy.deepcopy(revised)
    corrected, mapping = reconcile_revision(initial, revised)
    assert revised == before
    assert corrected["sources"][0]["title"] == "Revised title"
    assert corrected["observations"][0]["value"] == 999
    assert corrected["sources"][0]["id"] != source_id
    assert corrected["observations"][0]["id"] != observation_id
    assert corrected["observations"][0]["source_id"] == corrected["sources"][0]["id"]
    for old, new in zip(before["analysis"]["claims"], corrected["analysis"]["claims"], strict=True):
        assert new["evidence_ids"] == [
            mapping["observations"].get(item, item) for item in old["evidence_ids"]
        ]
    validate_revision(initial, corrected)


def test_reconciliation_no_changes_keeps_identifiers(evidence, analysis):
    from market_briefing.research import reconcile_revision

    initial = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    corrected, mapping = reconcile_revision(initial, initial)
    assert corrected == initial
    assert mapping == {"sources": {}, "observations": {}}


@pytest.mark.parametrize("collection", ["sources", "observations"])
def test_reconciliation_rejects_ambiguous_duplicates(evidence, analysis, collection):
    from market_briefing.research import reconcile_revision

    initial = {
        "sources": evidence["sources"],
        "observations": evidence["observations"],
        "analysis": analysis,
    }
    revised = copy.deepcopy(initial)
    revised[collection].append(copy.deepcopy(revised[collection][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile_revision(initial, revised)
