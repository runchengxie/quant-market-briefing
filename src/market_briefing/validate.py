"""Conservative mechanical checks; never a semantic/source audit."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .analysis import validate_analysis
from .contracts import validate_document

NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
BANNED = re.compile(r'[#*\x60\[\]<>\n\r";；“”‘’—–-]|[\U0001F000-\U0001FAFF\u2600-\u27BF]')
ESTIMATE = re.compile(r"预计|预期|预测|估计|可能|假设|预估")
FORECAST_ONLY = re.compile(r"不是.+而是|总体来说|综上|总而言之|值得注意的是")


def _numbers(text: str) -> set[Decimal]:
    return {Decimal(item) for item in NUMBER.findall(text)}


def _allowed_numbers(observations: list[dict]) -> set[Decimal]:
    allowed = set()
    for item in observations:
        if isinstance(item["value"], str):
            allowed |= _numbers(item["value"])
        elif item["value"] is not None:
            allowed.add(Decimal(str(item["value"])))
    return allowed


def _claim_numbers(text: str, market_date: str, observations: list[dict]) -> set[Decimal]:
    # Dates and horizon numbers may occur only inside their actual expressions.
    year, month, day = [int(part) for part in market_date.split("-")]
    text = re.sub(r"(?<!\d)6(?:至|到)12个月", "", text)
    text = re.sub(rf"(?<!\d)(?:{year}年)?0?{month}月0?{day}日", "", text)
    for item in observations:
        text = text.replace(item["reference_period"], "")
        for literal in re.findall(r"\d{4}-\d{2}-\d{2}", item["reference_period"]):
            try:
                period_date = date.fromisoformat(literal)
            except ValueError:
                continue
            text = re.sub(
                rf"(?<!\d)(?:{period_date.year}年)?0?{period_date.month}月0?{period_date.day}日",
                "",
                text,
            )
    return _numbers(text)


def validate_draft(evidence: dict, analysis: dict, briefing: dict) -> dict:
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
        validate_document(briefing, "briefing")
    except (ValueError, KeyError, TypeError) as exc:
        quality["structure_passed"] = False
        errors.append(str(exc))
        return quality
    try:
        validate_analysis(analysis, evidence)
    except ValueError as exc:
        quality["evidence_links_passed"] = False
        errors.append(str(exc))
        return quality
    if (
        briefing["market_date"] != evidence["market_date"]
        or briefing["evidence_cutoff"] != evidence["evidence_cutoff"]
    ):
        errors.append("Briefing date/cutoff differs from evidence")
        quality["evidence_links_passed"] = False
    if briefing["sources"] != evidence["sources"] or briefing["thesis"] != analysis["thesis"]:
        errors.append("Briefing changes trusted sources/thesis")
        quality["evidence_links_passed"] = False
    claims = {c["id"]: c for c in analysis["claims"]}
    observations = {o["id"]: o for o in evidence["observations"]}
    all_linked = []
    for index, paragraph in enumerate(briefing["paragraphs"], 1):
        text = paragraph["text"]
        if BANNED.search(text) or not text.strip() or re.match(r"^\s*\d+[.、)]", text):
            errors.append(f"Paragraph {index} violates plain Chinese formatting")
            quality["editorial_rules_passed"] = False
        if FORECAST_ONLY.search(text) or re.search(r"[A-Za-z]{4,}", text):
            warnings.append(f"Paragraph {index}: review formulaic phrasing or English wording")
        if not set(paragraph["claim_ids"]) <= claims.keys():
            errors.append(f"Paragraph {index} has unknown claims")
            quality["evidence_links_passed"] = False
            continue
        linked_claims = [claims[key] for key in paragraph["claim_ids"]]
        linked = [observations[key] for claim in linked_claims for key in claim["evidence_ids"]]
        all_linked.extend(linked)
        if any(
            c["temporal_type"] in {"estimate", "mixed"} for c in linked_claims
        ) and not ESTIMATE.search(text):
            errors.append(f"Paragraph {index} loses estimate qualification")
            quality["evidence_links_passed"] = False
        try:
            if not _claim_numbers(text, evidence["market_date"], linked) <= _allowed_numbers(
                linked
            ):
                errors.append(f"Paragraph {index} introduces unsupported numbers")
                quality["evidence_links_passed"] = False
        except InvalidOperation:
            errors.append(f"Paragraph {index} contains invalid numbers")
            quality["evidence_links_passed"] = False
    if BANNED.search(briefing["headline"]):
        errors.append("Headline violates plain Chinese formatting")
        quality["editorial_rules_passed"] = False
    if not _claim_numbers(
        briefing["headline"], evidence["market_date"], all_linked
    ) <= _allowed_numbers(all_linked):
        errors.append("Headline introduces unsupported numbers")
        quality["evidence_links_passed"] = False
    length = len(briefing["brief_text"])
    if not 800 <= length <= 1200:
        warnings.append("Briefing is outside soft 800–1,200 character range")
    if len({p["text"] for p in briefing["paragraphs"]}) < 5:
        warnings.append("Repeated paragraphs require editorial review")
    warnings.append(
        "Numeric/format checks do not certify meaning, units, causality or source accuracy"
    )
    return quality
