"""Independent source decisions bound to exact weekly document bytes."""

from pathlib import Path

from ..contracts import aware_time
from ..review import file_hash
from .contracts import load_weekly_document, validate_weekly_document
from .validate import validate_weekly_draft


def verify_weekly_review(review: dict, evidence: Path, analysis: Path, briefing: Path) -> None:
    validate_weekly_document(review, "weekly-review")
    paths = {"evidence": evidence, "analysis": analysis, "briefing": briefing}
    if any(file_hash(path) != review["hashes"][name] for name, path in paths.items()):
        raise ValueError("Weekly source review hashes do not match documents")
    docs = {name: load_weekly_document(path, f"weekly-{name}") for name, path in paths.items()}
    brief = docs["briefing"]
    for key in ["week_start", "run_id", "revision", "product"]:
        if review[key] != brief[key]:
            raise ValueError(f"Weekly review {key} differs from briefing")
    if review["week_start"] != docs["evidence"]["week_start"]:
        raise ValueError("Review differs from evidence week")
    if aware_time(review["reviewed_at"]) < aware_time(brief["generated_at"]):
        raise ValueError("Review predates final weekly draft")
    quality = validate_weekly_draft(docs["evidence"], docs["analysis"], brief)
    if quality["errors"] or brief["status"] != "validated_draft" or brief["quality"] != quality:
        raise ValueError("Review cannot approve invalid or altered validation findings")
    claims = {key for section in brief["sections"] for key in section["claim_ids"]}
    decisions = {item["claim_id"]: item for item in review["decisions"]}
    if set(decisions) != claims:
        raise ValueError("Review must decide exactly every final weekly claim")
    if any(item["status"] != "approved" for item in decisions.values()):
        raise ValueError("Final weekly claims include unapproved source decisions")
