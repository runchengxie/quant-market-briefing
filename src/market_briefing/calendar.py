"""Completed XNYS sessions, including holidays, DST and early closes."""

from datetime import datetime
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from .storage import checked_date


def select_session(now: datetime, requested_date: str | None = None) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local_date = now.astimezone(ZoneInfo("America/New_York")).date()
    report_date = checked_date(requested_date) if requested_date else local_date.isoformat()
    year = int(report_date[:4])
    calendar = xcals.get_calendar("XNYS", start=f"{year - 1}-01-01", end=f"{year + 1}-12-31")
    if not calendar.is_session(report_date):
        if requested_date:
            raise ValueError("Requested date is not a trading session")
        return {"status": "skipped", "market_date": report_date, "reason": "non_trading_day"}
    close = calendar.session_close(report_date).to_pydatetime()
    if close > now:
        raise ValueError("Requested trading session has not closed")
    return {
        "status": "ready",
        "market_date": report_date,
        "scheduled_close": close.isoformat(),
        "replay": report_date != local_date.isoformat(),
    }
