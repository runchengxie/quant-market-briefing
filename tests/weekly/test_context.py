import copy
import json
from datetime import UTC, datetime

import pytest


def save_run(root, date, revision, evidence, analysis, editor_output):
    from market_briefing.editor import assemble_briefing

    run = root / date / revision
    run.mkdir(parents=True)
    brief = assemble_briefing(
        editor_output, evidence, analysis, f"us-{date}-{revision}", int(revision[1:])
    )
    for name, doc in [("evidence", evidence), ("analysis", analysis), ("briefing", brief)]:
        (run / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return run


def test_freezes_daily_leads_and_missing_days(tmp_path, evidence, analysis, editor_output):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.context import freeze_weekly_context, load_weekly_context

    cutoff = datetime(2026, 10, 4, tzinfo=UTC)
    week = select_week(cutoff, "2026-09-28")
    save_run(tmp_path, "2026-10-02", "r0001", evidence, analysis, editor_output)
    latest = save_run(tmp_path, "2026-10-02", "r0002", evidence, analysis, editor_output)
    (tmp_path / "2026-10-02/r0003").mkdir()
    context = load_weekly_context(tmp_path, None, week, cutoff)
    assert len(context["daily_runs"]) == 1
    assert context["daily_runs"][0]["revision"] == "r0002"
    assert context["daily_runs"][0]["audit_status"] == "unreviewed"
    assert context["previous_view"]["status"] == "absent"
    assert "2026-09-28" in " ".join(context["missing_inputs"])
    assert context["daily_runs"][0]["evidence"]["sources"][0]["id"].startswith(
        "daily_2026-10-02_r0002_"
    )
    out = tmp_path / "frozen"
    out.mkdir()
    metadata = freeze_weekly_context(context, out)
    assert len(metadata["context_sha256"]) == 64
    original = (out / "weekly-context.json").read_bytes()
    (latest / "evidence.json").write_text("{}")
    assert (out / "weekly-context.json").read_bytes() == original


def test_invalid_review_is_not_approval(tmp_path, evidence, analysis, editor_output):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.context import load_weekly_context

    cutoff = datetime(2026, 10, 4, tzinfo=UTC)
    run = save_run(tmp_path, "2026-10-02", "r0001", evidence, analysis, editor_output)
    (run / "review.json").write_text("{}")
    with pytest.raises(ValueError):
        load_weekly_context(tmp_path, None, select_week(cutoff), cutoff)


@pytest.mark.parametrize("mode", ["oversize", "too_many", "symlink", "future"])
def test_context_boundary(tmp_path, evidence, analysis, editor_output, mode):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.context import load_weekly_context

    cutoff = datetime(2026, 10, 4, tzinfo=UTC)
    run = save_run(tmp_path, "2026-10-02", "r0001", evidence, analysis, editor_output)
    if mode == "oversize":
        (run / "evidence.json").write_bytes(b" " * (2 * 1024 * 1024 + 1))
    if mode == "too_many":
        for n in range(2, 34):
            (tmp_path / f"2026-10-02/r{n:04d}").mkdir()
    if mode == "symlink":
        external = tmp_path.parent / (tmp_path.name + "-outside.json")
        external.write_text((run / "evidence.json").read_text(encoding="utf-8"), encoding="utf-8")
        (run / "evidence.json").unlink()
        try:
            (run / "evidence.json").symlink_to(external)
        except OSError:
            pytest.skip("Windows symlink privilege unavailable")
    if mode == "future":
        doc = copy.deepcopy(evidence)
        doc["collected_at"] = "2027-01-01T00:00:00Z"
        (run / "evidence.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        load_weekly_context(tmp_path, None, select_week(cutoff), cutoff)


def test_missing_context_is_optional():
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.context import load_weekly_context

    now = datetime(2026, 10, 4, tzinfo=UTC)
    assert load_weekly_context(None, None, select_week(now), now)["daily_runs"] == []


def test_previous_week_identity(tmp_path, weekly_evidence, weekly_analysis, weekly_briefing):
    from market_briefing.weekly.calendar import select_week
    from market_briefing.weekly.context import load_weekly_context

    for name, doc in [
        ("evidence", weekly_evidence),
        ("analysis", weekly_analysis),
        ("briefing", weekly_briefing),
    ]:
        (tmp_path / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    now = datetime(2026, 10, 10, 8, tzinfo=UTC)
    context = load_weekly_context(None, tmp_path, select_week(now), now)
    assert context["previous_view"]["status"] == "available"
    assert context["previous_view"]["week_start"] == "2026-09-28"
    assert context["previous_view"]["audit_status"] == "unreviewed"
    with pytest.raises(ValueError):
        load_weekly_context(None, tmp_path, select_week(now, "2026-09-28"), now)
