"""External, immutable runtime files."""

import json
import os
import re
import uuid
from datetime import date
from pathlib import Path

from filelock import FileLock


def checked_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected ISO report date")
    date.fromisoformat(value)
    return value


def assert_external_path(path: Path) -> Path:
    resolved = Path(path).resolve()
    if any((parent / ".git").exists() for parent in [resolved, *resolved.parents]):
        raise ValueError("Runtime destination must be outside source repositories")
    return resolved


def write_atomic(path: Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with raw.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(raw, path)
    finally:
        raw.unlink(missing_ok=True)


def date_lock(root: Path, market_date: str) -> FileLock:
    checked_date(market_date)
    lock_root = Path(root) / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    return FileLock(lock_root / f"{market_date}.lock", timeout=0)


def allocate_revision(root: Path, market_date: str) -> tuple[Path, int]:
    checked_date(market_date)
    date_root = Path(root) / market_date
    date_root.mkdir(parents=True, exist_ok=True)
    if date_root.is_symlink():
        raise ValueError("Report directory cannot be a symlink")
    existing = [
        int(path.name[1:]) for path in date_root.iterdir() if re.fullmatch(r"r\d{4,}", path.name)
    ]
    revision = max(existing, default=0) + 1
    run_dir = date_root / f"r{revision:04d}"
    run_dir.mkdir()
    return run_dir, revision
