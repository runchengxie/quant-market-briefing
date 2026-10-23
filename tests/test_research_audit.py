import copy

import pytest

from market_briefing.editor import assemble_briefing
from market_briefing.prior import freeze_prior, load_prior
from market_briefing.research_audit import verify_audit, write_audit
from market_briefing.research_state import build_continuity
from market_briefing.storage import write_atomic
from market_briefing.validate import validate_draft


def test_marked_audit_requires_unchanged_sidecars(
    tmp_path, evidence, analysis, editor_output, research_state
):
    for name, doc in [("evidence", evidence), ("analysis", analysis)]:
        write_atomic(tmp_path / f"{name}.json", doc)
    prior = freeze_prior(load_prior(None, evidence["market_date"], None), tmp_path)
    members = {
        "prior-inventory.json": prior,
        "research-state.json": research_state,
        "continuity.json": build_continuity(prior, research_state),
    }
    audit = write_audit(tmp_path, members)
    brief = assemble_briefing(editor_output, evidence, analysis, "run", 1, audit=audit)
    assert not validate_draft(evidence, analysis, brief, audit=audit)["errors"]
    verify_audit(tmp_path, brief, evidence, analysis)
    assert validate_draft(evidence, analysis, brief)["errors"]
    (tmp_path / "research-state.json").unlink()
    with pytest.raises(OSError):
        verify_audit(tmp_path, brief, evidence, analysis)


def test_foreign_audit_member_rejected(tmp_path, evidence, analysis):
    for name, doc in [("evidence", evidence), ("analysis", analysis)]:
        write_atomic(tmp_path / f"{name}.json", doc)
    with pytest.raises(ValueError):
        write_audit(tmp_path, {"../foreign.json": copy.deepcopy(analysis)})


def test_public_v1_cannot_publish_unassessable_long_term(
    tmp_path, evidence, analysis, editor_output, research_state
):
    for name, doc in [("evidence", evidence), ("analysis", analysis)]:
        write_atomic(tmp_path / f"{name}.json", doc)
    prior = freeze_prior(load_prior(None, evidence["market_date"], None), tmp_path)
    research_state["long_term"].update(
        assessment_status="insufficient", direction=None, confidence=None, gap="缺少盈利覆盖"
    )
    audit = write_audit(
        tmp_path,
        {
            "prior-inventory.json": prior,
            "research-state.json": research_state,
            "continuity.json": build_continuity(prior, research_state),
        },
    )
    brief = assemble_briefing(editor_output, evidence, analysis, "run", 1, audit=audit)
    assert brief["status"] == "draft"
    assert brief["quality"]["errors"]
