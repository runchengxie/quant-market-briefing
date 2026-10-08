from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/New_York"))


@pytest.mark.parametrize(
    "now,start,final",
    [
        ("2026-10-10T00:00:00", "2026-10-05", "2026-10-09"),
        ("2026-10-09T23:59:58", "2026-09-28", "2026-10-02"),
        ("2026-04-04T08:00:00", "2026-03-30", "2026-04-02"),
        ("2026-11-28T08:00:00", "2026-11-23", "2026-11-27"),
    ],
)
def test_completed_week(now, start, final):
    from market_briefing.weekly.calendar import select_week

    week = select_week(at(now))
    assert week["week_start"] == start
    assert week["final_session"] == final
    if final == "2026-11-27":
        assert week["scheduled_close"] == "2026-11-27T18:00:00+00:00"


def test_dst_window_and_historical_cutoff():
    from market_briefing.weekly.calendar import select_week

    week = select_week(at("2026-03-10T10:00:00"), "2026-03-02")
    assert week["week_end_exclusive"] == "2026-03-09T00:00:00-04:00"
    assert week["retrospective_end"] == week["week_end_exclusive"]
    assert week["baseline_session"] == "2026-02-27"


@pytest.mark.parametrize(
    "now,requested",
    [
        (datetime(2026, 10, 10), "latest"),
        (at("2026-10-10T10:00:00"), "2026-10-06"),
        (at("2026-10-08T10:00:00"), "2026-10-05"),
    ],
)
def test_invalid_week(now, requested):
    from market_briefing.weekly.calendar import select_week

    with pytest.raises(ValueError):
        select_week(now, requested)


def test_no_sessions_skips(monkeypatch):
    from market_briefing.weekly import calendar

    original = calendar.xcals.get_calendar

    class Empty:
        def sessions_in_range(self, *args):
            return []

    monkeypatch.setattr(calendar.xcals, "get_calendar", lambda *a, **k: Empty())
    assert calendar.select_week(at("2026-10-10T10:00:00"))["status"] == "skipped"
    monkeypatch.setattr(calendar.xcals, "get_calendar", original)


def test_roots_revisions_and_lock(tmp_path):
    from filelock import Timeout

    from market_briefing.weekly.storage import allocate_week, resolve_data_root, week_lock

    settings = tmp_path / "workspace.toml"
    settings.write_text(f'data_root = "{tmp_path.as_posix()}"\n')
    root = resolve_data_root(None, settings)
    assert root == tmp_path / "quant-market-briefing"
    assert resolve_data_root(tmp_path / "override", settings) == tmp_path / "override"
    with week_lock(root, "2026-09-28"):
        first, revision = allocate_week(root, "2026-09-28")
        assert first == root / "weekly/2026-09-28/r0001"
        assert revision == 1
        with pytest.raises(Timeout), week_lock(root, "2026-09-28"):
            pass
    assert allocate_week(root, "2026-09-28")[1] == 2
    with pytest.raises(ValueError):
        resolve_data_root(None, None)
    settings.write_text("invalid toml [")
    with pytest.raises(ValueError):
        resolve_data_root(None, settings)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(ValueError):
        resolve_data_root(repo, None)
