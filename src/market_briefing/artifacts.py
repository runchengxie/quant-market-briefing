"""Bounded, duplicate-safe reads of explicit artifact roots."""

import hashlib
import json
from pathlib import Path

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024


def decode_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject(value):
        raise ValueError(f"Non-finite JSON constant: {value}")

    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(result, dict):
        raise ValueError("Artifact must be a JSON object")
    return result


def read_bounded(path: Path, owner: Path) -> tuple[dict, bytes]:
    path, owner = Path(path).absolute(), Path(owner).absolute()
    if owner.is_symlink() or not path.resolve().is_relative_to(owner.resolve()):
        raise ValueError("Artifact escapes supplied root")
    cursor = path
    while cursor != owner:
        if cursor.is_symlink() or cursor == cursor.parent:
            raise ValueError("Artifact cannot traverse symlinks")
        cursor = cursor.parent
    before = path.stat()
    if before.st_size > MAX_FILE:
        raise ValueError("Artifact exceeds size limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    after = path.stat()
    if len(raw) != before.st_size or (after.st_size, after.st_mtime_ns) != (
        before.st_size,
        before.st_mtime_ns,
    ):
        raise ValueError("Artifact changed during read")
    return decode_json(raw), raw


def raw_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
