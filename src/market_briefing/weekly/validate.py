"""Mechanical checks for weekly prose; independent source review remains required."""

import re
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from ..contracts import aware_time
from .contracts import linked_records, validate_weekly_analysis, validate_weekly_document


def numeric_tokens(
    text: str, records: list[dict], dates: list[str], *, source_text: bool = False
) -> set[Decimal]:
    dates = list(dates)
    text = re.sub(r"(?<!\d)(?:一至四|1(?:至|到|[-–])4)(?:周|星期)", "", text)
    digits = {char: index for index, char in enumerate("零一二三四五六七八九")}
    digits.update(〇=0, 两=2)

    def chinese_count(match):
        raw = match.group(1)
        if "十" in raw:
            left, right = raw.split("十", 1)
            if len(left) <= 1 and len(right) <= 1:
                return str((digits.get(left, 1) if left else 1) * 10 + digits.get(right, 0))
        elif len(raw) == 1:
            return str(digits[raw])
        return raw

    if source_text:
        text = re.sub(
            r"([零〇一二两三四五六七八九十]{1,3})(?=个?月|年|周|天|日|人|家|桶|次)",
            chinese_count,
            text,
        )
    timestamps = []
    for record in records:
        for key in [
            "event_at",
            "start_at",
            "end_at",
            "observed_at",
            "known_at",
            "published_at",
            "reference_period",
        ]:
            value = record.get(key) or ""
            dates.extend(re.findall(r"\d{4}-\d{2}-\d{2}", value))
            if key != "reference_period" and value:
                timestamps.append(value)
        period = record.get("reference_period", "")
        for year, month in re.findall(r"(\d{4})(?:-|年)(\d{1,2})(?!\d)", period):
            text = re.sub(rf"(?<!\d)(?:{year}年)?0?{int(month)}月(?!\d)", "", text)
        for literal in re.findall(r"\d{1,2}月\d{1,2}日", period):
            text = text.replace(literal, "")
    timestamps.extend(value for value in dates if "T" in value)
    for timestamp in timestamps:
        parsed = aware_time(timestamp)
        text = text.replace(timestamp, "")
        for clock in [parsed, parsed.astimezone(ZoneInfo("America/New_York"))]:
            suffix = f".{clock.microsecond:06d}".rstrip("0") if clock.microsecond else ""
            for literal in [
                f"{clock.hour:02d}:{clock.minute:02d}:{clock.second:02d}{suffix}",
                f"{clock.hour:02d}:{clock.minute:02d}:{clock.second:02d}",
                f"{clock.hour:02d}:{clock.minute:02d}",
            ]:
                text = re.sub(rf"(?<![\d:]){re.escape(literal)}(?![\d:.])", "", text)
    dates = [value[:10] for value in dates]
    allowed_dates = {date.fromisoformat(value) for value in dates}

    def date_range(match):
        year, month, first, second_month, last = match.groups()
        for candidate_year in {d.year for d in allowed_dates}:
            if year and int(year) != candidate_year:
                continue
            try:
                begin = date(candidate_year, int(month), int(first))
                end = date(candidate_year, int(second_month or month), int(last))
            except ValueError:
                continue
            if begin in allowed_dates and end in allowed_dates:
                return ""
        return match.group(0)

    text = re.sub(
        r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?(?:至|到|[-–])(?:(\d{1,2})月)?(\d{1,2})日",
        date_range,
        text,
    )
    for value in set(dates):
        day = date.fromisoformat(value)
        text = text.replace(value, "")
        text = re.sub(rf"(?<!\d)(?:{day.year}年)?0?{day.month}月0?{day.day}日", "", text)
    if any(
        (record.get("instrument") or "").replace(" ", "").upper() in {"S&P500", "SPX", "^GSPC"}
        for record in records
    ):
        text = re.sub(r"标普\s*500|S&P\s*500", "", text)
    return {Decimal(number) for number in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)}


def scope_literals(evidence: dict) -> list[str]:
    end = aware_time(evidence["week_end_exclusive"])
    cutoff = aware_time(evidence["evidence_cutoff"])
    return [
        evidence["week_start"],
        evidence["baseline_session"],
        evidence["final_session"],
        end.date().isoformat(),
        (end - timedelta(days=1)).date().isoformat(),
        (end + timedelta(days=6)).date().isoformat(),
        cutoff.isoformat(),
        cutoff.astimezone(ZoneInfo("America/New_York")).isoformat(),
    ]


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
    headline_records = linked_records(
        [
            key
            for section in briefing["sections"]
            for claim_id in section["claim_ids"]
            if claim_id in claims
            for key in claims[claim_id]["evidence_ids"]
        ],
        evidence,
    )
    headline_allowed = set()
    for record in headline_records:
        if isinstance(record.get("value"), (int, float)):
            headline_allowed.add(abs(Decimal(str(record["value"]))))
        for field in ["value", "title", "development"]:
            if isinstance(record.get(field), str):
                headline_allowed |= numeric_tokens(record[field], [record], [], source_text=True)
    if (
        not numeric_tokens(
            briefing["headline"],
            headline_records,
            scope_literals(evidence),
        )
        <= headline_allowed
    ):
        errors.append("Headline introduces unsupported numbers")
    for section in briefing["sections"]:
        text = section["heading"] + "\n" + section["text"]
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
                    allowed |= numeric_tokens(record[key], [record], [], source_text=True)
        if (
            not numeric_tokens(
                text,
                records,
                scope_literals(evidence),
            )
            <= allowed
        ):
            errors.append(f"Section {section['topic']} introduces unsupported numbers")
        if any(c["temporal_type"] in {"estimate", "mixed"} for c in linked) and not re.search(
            r"预计|预期|预测|估计|估算|可能|假设|预估|初值|初估|初步|指引|拟|计划|承诺|指示性|插值|若.+(?:应|需|将)|如果.+(?:应|需|将)",
            text,
        ):
            errors.append("Section loses estimate qualification")
        if (
            any(c["temporal_type"] == "scheduled" for c in linked)
            or any("status" in record for record in records)
        ) and not re.search(r"日程|预定|计划|下周|将|拟|待|预计", text):
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
