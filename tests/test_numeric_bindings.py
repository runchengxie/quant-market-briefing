import copy
import json

import pytest

from market_briefing.editor import assemble_briefing
from market_briefing.numeric_bindings import render_candidate, verify_bindings
from market_briefing.validate import validate_draft


@pytest.fixture
def candidate(bound_editor_output):
    return bound_editor_output


def bound_brief(candidate, evidence, analysis):
    output, record = render_candidate(candidate, evidence, analysis)
    brief = assemble_briefing(output, evidence, analysis, "run", 1, bindings=record)
    return brief, record


def test_render_preserves_public_shape_and_records_provenance(candidate, evidence, analysis):
    brief, record = bound_brief(candidate, evidence, analysis)
    assert brief["status"] == "validated_draft"
    assert "{{" not in brief["brief_text"]
    assert "0.73个百分点" in brief["brief_text"]
    assert "12个百分点（2026年第三季度）" in brief["brief_text"]
    assert record["bindings"][0]["observation_id"] == "e1"
    assert record["bindings"][0]["metric"] == "sp500_return"
    assert record["bindings"][0]["unit"] == "percentage_points"
    assert not validate_draft(evidence, analysis, brief, bindings=record)["errors"]
    assert not brief["quality"]["source_audit_passed"]


@pytest.mark.parametrize(
    "text",
    [
        "指数上涨{{value:ghost}}。",
        "指数上涨{{value:e2}}。",
        "指数上涨12%。",
        "指数上涨零点七三%。",
        "指数报三千点。",
        "新增七个。",
        "指数变动A9%。",
        "指数上涨百分之七。",
        "指数上涨{{value:e1}}亿美元。",
        "指数上涨负{{value:e1}}。",
        "指数上涨{{value:e1}}%。",
        "指数上涨{{value:e1}}美元。",
        "指数上涨{{value:e1}。",
    ],
)
def test_rejects_unknown_unlinked_raw_and_relabelled_quantities(
    candidate,
    evidence,
    analysis,
    text,
):
    candidate["paragraphs"][0]["text"] = text
    # Even a number present elsewhere in the paragraph's evidence must be bound.
    if text == "指数上涨12%。":
        candidate["paragraphs"][0]["claim_ids"].append("c2")
    with pytest.raises(ValueError):
        render_candidate(candidate, evidence, analysis)


def test_headline_is_bound_to_final_claims(candidate, evidence, analysis):
    candidate["headline"] = "合成指数变化{{value:e1}}"
    brief, record = bound_brief(candidate, evidence, analysis)
    assert brief["headline"] == "合成指数变化0.73个百分点"
    verify_bindings(record, evidence, analysis, brief)


@pytest.mark.parametrize(
    "change", ["value", "unit", "reference_period", "analysis", "text", "record"]
)
def test_revalidation_rejects_stale_inputs_and_modified_output(
    candidate,
    evidence,
    analysis,
    change,
):
    brief, record = bound_brief(candidate, evidence, analysis)
    if change == "analysis":
        analysis["claims"][0]["text"] = "另一个判断"
    elif change == "text":
        brief["paragraphs"][0]["text"] = brief["paragraphs"][0]["text"].replace("0.73", "12")
        brief["brief_text"] = "\n\n".join(p["text"] for p in brief["paragraphs"])
    elif change == "record":
        record["bindings"][0]["unit"] = "usd"
    else:
        evidence["observations"][0][change] = {
            "value": 12,
            "unit": "usd",
            "reference_period": "2026-09-01",
        }[change]
    assert validate_draft(evidence, analysis, brief, bindings=record)["errors"]


def test_missing_binding_record_fails_closed(candidate, evidence, analysis):
    brief, _ = bound_brief(candidate, evidence, analysis)
    assert validate_draft(evidence, analysis, brief)["errors"]


def test_counterfactual_follows_only_changed_fact(candidate, evidence, analysis):
    original, _ = render_candidate(candidate, evidence, analysis)
    changed = copy.deepcopy(evidence)
    changed["observations"][0]["value"] = -2.5
    revised, _ = render_candidate(candidate, changed, analysis)
    assert "负2.5个百分点" in revised["paragraphs"][0]["text"]
    assert revised["paragraphs"][1:] == original["paragraphs"][1:]


def test_record_json_roundtrip(candidate, evidence, analysis):
    brief, record = bound_brief(candidate, evidence, analysis)
    verify_bindings(json.loads(json.dumps(record)), evidence, analysis, brief)


@pytest.mark.parametrize(
    "unit,display",
    [
        ("percentage_points", "7个百分点"),
        ("percent", "7%"),
        ("basis_points", "7个基点"),
        ("count", "7个"),
        ("usd", "7美元"),
        ("ratio", "7倍"),
        ("index_level", "7点"),
    ],
)
def test_canonical_units_are_rendered_without_conversion(
    candidate, evidence, analysis, unit, display
):
    evidence["observations"][0].update(value=7, unit=unit)
    rendered, _ = render_candidate(candidate, evidence, analysis)
    assert display in rendered["paragraphs"][0]["text"]


def test_non_session_date_is_retained(candidate, evidence, analysis):
    evidence["observations"][0]["reference_period"] = "2026-09-01"
    rendered, _ = render_candidate(candidate, evidence, analysis)
    assert "0.73个百分点（2026年9月1日）" in rendered["paragraphs"][0]["text"]


def test_live_edit_rejects_raw_quantities(tmp_path, evidence, analysis, editor_output, monkeypatch):
    from market_briefing.editor import edit

    monkeypatch.setattr("market_briefing.editor.execute_stage", lambda *a, **kw: editor_output)
    with pytest.raises(ValueError, match="unbound numeric"):
        edit(analysis, evidence, {"run_dir": tmp_path, "run_id": "run", "revision": 1})
    assert not (tmp_path / "numeric-bindings.json").exists()


def test_live_edit_and_bundle_require_same_binding_record(
    tmp_path,
    candidate,
    evidence,
    analysis,
    monkeypatch,
):
    from datetime import UTC, datetime

    from market_briefing.cli import main
    from market_briefing.editor import edit
    from market_briefing.publication import build_bundle
    from market_briefing.review import file_hash
    from market_briefing.storage import write_atomic

    monkeypatch.setattr("market_briefing.editor.execute_stage", lambda *a, **kw: candidate)
    brief = edit(analysis, evidence, {"run_dir": tmp_path, "run_id": "run", "revision": 1})
    for name, data in [("evidence", evidence), ("analysis", analysis), ("briefing", brief)]:
        write_atomic(tmp_path / f"{name}.json", data)
    review = {
        "schema_version": "market.source-review.v1",
        "market_date": evidence["market_date"],
        "reviewer": "Synthetic reviewer",
        "reviewed_at": datetime.now(UTC).isoformat(),
        "hashes": {
            name: file_hash(tmp_path / f"{name}.json")
            for name in ["evidence", "analysis", "briefing"]
        },
        "decisions": [
            {"claim_id": c["id"], "status": "approved", "reason": "Synthetic only"}
            for c in analysis["claims"]
        ],
    }
    write_atomic(tmp_path / "review.json", review)
    assert main(["validate", "--run-dir", str(tmp_path)]) == 0
    path = tmp_path / "numeric-bindings.json"
    original = path.read_bytes()
    path.unlink()
    assert main(["validate", "--run-dir", str(tmp_path)]) == 2
    with pytest.raises(ValueError):
        build_bundle(tmp_path, tmp_path / "review.json", "a" * 40, "internal")
    path.write_bytes(original)
    manifest = build_bundle(tmp_path, tmp_path / "review.json", "a" * 40, "internal")
    assert (manifest.parent / path.name).read_bytes() == original
    assert len(json.loads(manifest.read_text())["artifacts"]) == 2
