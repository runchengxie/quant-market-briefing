from datetime import datetime

import pytest

from market_briefing.calendar import select_session


@pytest.mark.parametrize("now,requested,status,close", [
    ("2026-10-02T20:05:00Z", None, "ready", "2026-10-02T20:00:00+00:00"),
    ("2026-07-03T22:00:00Z", None, "skipped", None),
    ("2026-11-27T18:05:00Z", None, "ready", "2026-11-27T18:00:00+00:00"),
    ("2026-11-06T21:05:00Z", None, "ready", "2026-11-06T21:00:00+00:00"),
    ("2026-10-03T22:00:00Z", "2026-10-02", "ready", "2026-10-02T20:00:00+00:00"),
])
def test_sessions(now, requested, status, close):
    result = select_session(datetime.fromisoformat(now), requested)
    assert result["status"] == status
    if close:
        assert result["scheduled_close"] == close


@pytest.mark.parametrize("now,requested", [
    ("2026-10-02T19:00:00Z", "2026-10-02"),
    ("2026-10-02T22:00:00Z", "2026-10-05"),
    ("2026-10-02T22:00:00Z", "2026-07-03"),
    ("2026-10-02T22:00:00", "2026-10-02"),
    ("2026-10-02T22:00:00Z", "../escape"),
])
def test_reject_unready_session(now, requested):
    with pytest.raises(ValueError):
        select_session(datetime.fromisoformat(now), requested)
