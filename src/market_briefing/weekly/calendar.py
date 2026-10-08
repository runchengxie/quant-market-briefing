"""New York civil weeks with explicit market comparison endpoints."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from ..storage import checked_date


def select_week(now: datetime, requested: str = "latest") -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo("America/New_York")
    local = now.astimezone(zone)
    monday = local.date() - timedelta(days=local.weekday())
    if requested != "latest":
        monday = datetime.fromisoformat(checked_date(requested)).date()
        if monday.weekday() != 0:
            raise ValueError("week-start must be a Monday")
    gate = datetime.combine(monday + timedelta(days=4), time(23, 59, 59), zone)
    if gate > now:
        if requested != "latest":
            raise ValueError("Requested week is incomplete")
        monday -= timedelta(days=7)
    start = datetime.combine(monday, time(), zone)
    end = start + timedelta(days=7)
    calendar = xcals.get_calendar(
        "XNYS", start=f"{monday.year - 1}-01-01", end=f"{monday.year + 1}-12-31"
    )
    sessions = calendar.sessions_in_range(
        monday.isoformat(), (monday + timedelta(days=6)).isoformat()
    )
    metadata = {
        "week_start": monday.isoformat(),
        "week_end_exclusive": end.isoformat(),
        "retrospective_end": min(end, local).isoformat(),
        "timezone": "America/New_York",
    }
    if len(sessions) == 0:
        return {**metadata, "status": "skipped", "reason": "no_trading_sessions"}
    baseline = calendar.previous_session(sessions[0])
    return {
        **metadata,
        "status": "ready",
        "baseline_session": baseline.date().isoformat(),
        "final_session": sessions[-1].date().isoformat(),
        "scheduled_close": calendar.session_close(sessions[-1]).to_pydatetime().isoformat(),
    }
