"""Strict file contracts and semantic integrity checks."""

import json
import math
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def schema_path(kind: str) -> Path:
    if kind not in {
        "evidence",
        "analysis",
        "editor",
        "briefing",
        "review",
        "research",
        "intel-context",
    }:
        raise ValueError(f"Unknown document kind: {kind}")
    return Path(str(files("market_briefing").joinpath("resources", "schemas", f"{kind}.v1.json")))


def aware_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must contain a timezone")
    return parsed


def _unique(items: list[dict], key: str) -> None:
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {key}")


def validate_document(payload: dict, kind: str) -> None:
    schema = json.loads(schema_path(kind).read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload))
    if errors:
        raise ValueError(f"{kind}: {errors[0].message}")
    if kind == "evidence":
        _unique(payload["sources"], "id")
        _unique(payload["observations"], "id")
        cutoff = aware_time(payload["evidence_cutoff"])
        if aware_time(payload["scheduled_close"]) > cutoff:
            raise ValueError("Evidence cutoff precedes session close")
        if aware_time(payload["collected_at"]) < cutoff:
            raise ValueError("Collection precedes evidence cutoff")
        sources = {source["id"] for source in payload["sources"]}
        for source in payload["sources"]:
            if source["published_at"] and aware_time(source["published_at"]) > cutoff:
                raise ValueError("Source published after evidence cutoff")
        for item in payload["observations"]:
            if item["source_id"] not in sources:
                raise ValueError("Unresolved source ID")
            if aware_time(item["observed_at"]) > cutoff:
                raise ValueError("Observation after evidence cutoff")
            value = item["value"]
            if value is not None and (isinstance(value, str) != (item["unit"] == "text")):
                raise ValueError("Observation value type does not match unit")
            if isinstance(value, str) and not value.strip():
                raise ValueError("Empty text observation")
            if isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError("Non-finite observation")
    elif kind == "analysis":
        _unique(payload["claims"], "id")
        topics = [section["topic"] for section in payload["sections"]]
        if set(topics) != {
            "fundamentals",
            "support",
            "risks",
            "sector_macro",
            "catalysts",
            "conclusion",
        }:
            raise ValueError("Missing analysis section")
        known = {claim["id"] for claim in payload["claims"]}
        if any(not set(section["claim_ids"]) <= known for section in payload["sections"]):
            raise ValueError("Unresolved analysis claim ID")
    elif kind == "briefing":
        expected = "\n\n".join(paragraph["text"] for paragraph in payload["paragraphs"])
        if payload["brief_text"] != expected:
            raise ValueError("brief_text differs from paragraphs")
    elif kind == "review":
        _unique(payload["decisions"], "claim_id")


def load_document(path: Path, kind: str) -> dict:
    def reject_constant(value: str):
        raise ValueError(f"Invalid JSON constant: {value}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    validate_document(payload, kind)
    return payload
