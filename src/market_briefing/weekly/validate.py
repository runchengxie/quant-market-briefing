"""Mechanical checks for weekly prose; independent source review remains required."""

import re
from datetime import date
from decimal import Decimal

from .contracts import COLLECTIONS, validate_weekly_analysis, validate_weekly_document


def linked_records(ids: list[str], evidence: dict) -> list[dict]:
    records = {item["id"]: item for name in COLLECTIONS for item in evidence[name]}
    found = {}

    def visit(key):
        if key in found:
            return
        record = records[key]
        found[key] = record
        for reference in record.get("evidence_ids", []):
            visit(reference)

    for key in ids:
        visit(key)
    return list(found.values())


def numeric_tokens(text: str, records: list[dict], dates: list[str]) -> set[Decimal]:
    text = re.sub(r"(?<!\d)(?:一至四|1(?:至|到|[-–])4)(?:周|星期)", "", text)
    for record in records:
        for key in ["event_at", "start_at", "end_at", "observed_at", "reference_period"]:
            dates.extend(re.findall(r"\d{4}-\d{2}-\d{2}", record.get(key, "")))
    for value in set(dates):
        day = date.fromisoformat(value)
        text = text.replace(value, "")
        text = re.sub(rf"(?<!\d)(?:{day.year}年)?0?{day.month}月0?{day.day}日", "", text)
    return {Decimal(number) for number in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)}


def validate_weekly_draft(evidence: dict, analysis: dict, briefing: dict) -> dict:
    errors, warnings = [], []
    quality = {
        "structure_passed": True,
        "evidence_links_passed": True,
        "editorial_rules_passed": True,
        "source_audit_passed": False,
        "errors": errors,
        "warnings": warnings,
    }
    try:
        validate_weekly_document(briefing, "weekly-briefing")
    except (ValueError, KeyError, TypeError) as exc:
        quality["structure_passed"] = False
        errors.append(str(exc))
        return quality
    try:
        validate_weekly_analysis(analysis, evidence)
    except (ValueError, KeyError, TypeError) as exc:
        quality["evidence_links_passed"] = False
        errors.append(str(exc))
        return quality
    for key in [
        "week_start",
        "week_end_exclusive",
        "retrospective_end",
        "timezone",
        "evidence_cutoff",
        "sources",
    ]:
        if briefing[key] != evidence[key]:
            errors.append(f"Briefing changes trusted {key}")
    for key in ["thesis", "previous_view"]:
        if briefing[key] != analysis[key]:
            errors.append(f"Briefing changes trusted {key}")
    if briefing["missing_inputs"] != list(
        dict.fromkeys([*evidence["missing_inputs"], *analysis["missing_inputs"]])
    ):
        errors.append("Briefing changes missing inputs")
    claims = {claim["id"]: claim for claim in analysis["claims"]}
    for section in briefing["sections"]:
        text = section["text"]
        if not text.strip() or "\x00" in text:
            quality["editorial_rules_passed"] = False
            errors.append("Empty or invalid section text")
        if not set(section["claim_ids"]) <= claims.keys():
            errors.append("Unknown section claims")
            continue
        linked = [claims[key] for key in section["claim_ids"]]
        records = linked_records(
            [key for claim in linked for key in claim["evidence_ids"]], evidence
        )
        allowed = set()
        for record in records:
            value = record.get("value")
            if isinstance(value, (int, float)):
                allowed.add(abs(Decimal(str(value))))
            for key in ["value", "development", "title"]:
                if isinstance(record.get(key), str):
                    allowed |= numeric_tokens(record[key], [record], [])
        if (
            not numeric_tokens(
                text,
                records,
                [evidence["week_start"], evidence["final_session"], evidence["baseline_session"]],
            )
            <= allowed
        ):
            errors.append(f"Section {section['topic']} introduces unsupported numbers")
        if any(c["temporal_type"] in {"estimate", "mixed"} for c in linked) and not re.search(
            r"预计|预期|预测|估计|可能|假设|预估", text
        ):
            errors.append("Section loses estimate qualification")
        if any(c["temporal_type"] == "scheduled" for c in linked) and not re.search(
            r"日程|预定|计划|下周|将|拟|待|预计", text
        ):
            errors.append("Section presents scheduled event without qualification")
        if not linked and not re.search(r"缺|无|未|不足|有限|暂无", text):
            errors.append("Unlinked section must disclose missing coverage")
        if any(
            record.get("stale") or record.get("endpoint_status") == "lagged" for record in records
        ) and not re.search(r"滞后|截至|观测|缺|日期", text):
            errors.append("Section omits stale endpoint disclosure")
    quality["evidence_links_passed"] = not errors
    count = len(re.findall(r"[\u4e00-\u9fff]", briefing["brief_text"]))
    if not 1500 <= count <= 2500:
        warnings.append(f"Editorial length outside soft target: {count} Chinese characters")
    if any(source["published_at"] is None for source in evidence["sources"]):
        warnings.append("Unknown source publication timestamps require independent review")
    if evidence["missing_inputs"] or analysis["missing_inputs"]:
        warnings.append("Coverage has missing inputs; inspect the separate missing_inputs record")
    return quality
