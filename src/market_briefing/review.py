"""Source approval bound to all frozen document hashes."""
import hashlib
from pathlib import Path

from .contracts import aware_time, load_document, validate_document
from .validate import validate_draft


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_review(review: dict, evidence: Path, analysis: Path, briefing: Path) -> None:
    validate_document(review, "review")
    paths = {"evidence": evidence, "analysis": analysis, "briefing": briefing}
    if any(file_hash(path) != review["hashes"][kind] for kind, path in paths.items()):
        raise ValueError("Source review hashes do not match frozen documents")
    evidence_data = load_document(evidence, "evidence")
    analysis_data = load_document(analysis, "analysis")
    brief = load_document(briefing, "briefing")
    if review["market_date"] != evidence_data["market_date"]:
        raise ValueError("Source review has a different report date")
    if aware_time(review["reviewed_at"]) < aware_time(brief["generated_at"]):
        raise ValueError("Review predates final briefing")
    result = validate_draft(evidence_data, analysis_data, brief)
    if result["errors"] or brief["status"] != "validated_draft":
        raise ValueError("Source review cannot approve an invalid draft")
    if brief["quality"] != result:
        raise ValueError("Stored validation findings differ from recomputed checks")
    final_claims = {key for paragraph in brief["paragraphs"] for key in paragraph["claim_ids"]}
    decisions = {decision["claim_id"]: decision for decision in review["decisions"]}
    if set(decisions) != final_claims:
        raise ValueError("Review must decide exactly every final claim")
    if any(decision["status"] != "approved" for decision in decisions.values()):
        raise ValueError("Final claims include deferred/rejected source decisions")
