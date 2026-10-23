import json
from datetime import UTC, datetime

import pytest

from market_briefing.editor import assemble_briefing
from market_briefing.prior import freeze_prior, load_prior


def seed_prior(tmp_path, evidence, analysis, editor_output):
    brief = assemble_briefing(editor_output, evidence, analysis, "old", 1)
    brief["generated_at"] = "2026-10-03T00:00:00Z"
    for name, doc in [("evidence", evidence), ("analysis", analysis), ("briefing", brief)]:
        (tmp_path / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")


def test_prior_cutoff_includes_generation_time(tmp_path, evidence, analysis, editor_output):
    seed_prior(tmp_path, evidence, analysis, editor_output)
    with pytest.raises(ValueError):
        load_prior(tmp_path, "2026-10-05", datetime(2026, 10, 2, 23, tzinfo=UTC))
    prior = load_prior(tmp_path, "2026-10-05", datetime(2026, 10, 5, 22, tzinfo=UTC))
    assert prior["audit_status"] == "unreviewed"
    target = tmp_path / "new"
    target.mkdir()
    freeze_prior(prior, target)
    assert (target / "prior-inputs/evidence.json").read_bytes() == (
        tmp_path / "evidence.json"
    ).read_bytes()


def test_no_prior_is_absent():
    assert load_prior(None, "2026-10-05", datetime.now(UTC))["status"] == "absent"


def test_duplicate_keys_rejected(tmp_path, evidence, analysis, editor_output):
    seed_prior(tmp_path, evidence, analysis, editor_output)
    (tmp_path / "evidence.json").write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError):
        load_prior(tmp_path, "2026-10-05", datetime.now(UTC))
