"""Explicitly configured external weekly storage."""

import tomllib
from pathlib import Path

from filelock import FileLock

from ..storage import allocate_revision, assert_external_path, date_lock


def resolve_data_root(explicit: Path | None, settings: Path | None) -> Path:
    if explicit is not None:
        return assert_external_path(explicit)
    if settings is None:
        raise ValueError("Provide --data-root or --workspace-config with data_root")
    try:
        data = tomllib.loads(settings.read_text(encoding="utf-8"))
        value = data["data_root"]
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("data_root must be an absolute path")
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Cannot read workspace data_root") from exc
    return assert_external_path(Path(value) / "quant-market-briefing")


def week_lock(root: Path, week_start: str) -> FileLock:
    return date_lock(assert_external_path(root) / "weekly", week_start)


def allocate_week(root: Path, week_start: str) -> tuple[Path, int]:
    return allocate_revision(assert_external_path(root) / "weekly", week_start)
