"""Explicit previous-run snapshots, with no archive guessing or sentiment parsing."""

import copy
from datetime import datetime
from pathlib import Path

from .analysis import validate_analysis
from .artifacts import MAX_TOTAL, raw_digest, read_bounded
from .contracts import aware_time
from .storage import write_atomic
from .validate import validate_draft

INPUTS = (
    "evidence",
    "analysis",
    "briefing",
    "numeric-bindings",
    "research-state",
    "review",
    "research-audit",
)


def load_prior(run_dir: Path | None, market_date: str, cutoff: datetime) -> dict:
    if run_dir is None:
        return {
            "status": "absent",
            "identity": None,
            "audit_status": "unreviewed",
            "documents": {},
            "inventory": [],
            "_raw": {},
        }
    root = Path(run_dir)
    documents, inventory, raw_files = {}, [], {}
    budget = 0
    for name in INPUTS:
        path = root / f"{name}.json"
        if name not in {"evidence", "analysis", "briefing"} and not path.exists():
            continue
        document, raw = read_bounded(path, root)
        budget += len(raw)
        if budget > MAX_TOTAL:
            raise ValueError("Prior input budget exceeded")
        documents[name] = document
        raw_files[f"{name}.json"] = raw
        inventory.append({"name": f"{name}.json", "sha256": raw_digest(raw), "bytes": len(raw)})
    evidence, analysis, brief = (documents[k] for k in ["evidence", "analysis", "briefing"])
    validate_analysis(analysis, evidence)
    if not evidence["market_date"] < market_date or evidence["market_date"] != brief["market_date"]:
        raise ValueError("Prior market date must precede current date")
    if any(
        aware_time(value) > cutoff
        for value in [evidence["evidence_cutoff"], evidence["collected_at"], brief["generated_at"]]
    ):
        raise ValueError("Prior input is after current cutoff")
    if aware_time(evidence["evidence_cutoff"]) >= cutoff:
        raise ValueError("Prior cutoff must progress forward")
    audit = documents.get("research-audit")
    if "research-state" in documents and audit is None:
        raise ValueError("Prior structured state requires a binding research audit")
    if audit:
        from .research_audit import verify_audit

        verify_audit(root, brief, evidence, analysis)
    quality = validate_draft(
        evidence, analysis, brief, bindings=documents.get("numeric-bindings"), audit=audit
    )
    if quality["errors"] or quality != brief["quality"] or brief["status"] != "validated_draft":
        raise ValueError("Prior briefing has invalid or changed findings")
    audit_status = "unreviewed"
    if "review" in documents:
        from .review import verify_review

        verify_review(
            documents["review"], *(root / f"{k}.json" for k in ["evidence", "analysis", "briefing"])
        )
        if aware_time(documents["review"]["reviewed_at"]) > cutoff:
            raise ValueError("Prior review is after current cutoff")
        audit_status = "reviewed"
    # Recheck exact bytes after path-based review; models only receive the snapshot below.
    for name, raw in raw_files.items():
        if read_bounded(root / name, root)[1] != raw:
            raise ValueError("Prior input changed during validation")
    return {
        "status": "available",
        "identity": {
            "run_id": brief["run_id"],
            "revision": brief["revision"],
            "market_date": brief["market_date"],
            "evidence_cutoff": evidence["evidence_cutoff"],
            "generated_at": brief["generated_at"],
            "analysis_sha256": next(i["sha256"] for i in inventory if i["name"] == "analysis.json"),
        },
        "audit_status": audit_status,
        "documents": {k: v for k, v in documents.items() if k not in {"research-audit", "review"}},
        "inventory": inventory,
        "_raw": raw_files,
    }


def freeze_prior(prior: dict, destination: Path) -> dict:
    snapshot = copy.deepcopy({k: v for k, v in prior.items() if k != "_raw"})
    for name, raw in prior.get("_raw", {}).items():
        target = destination / "prior-inputs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    write_atomic(destination / "prior-inventory.json", snapshot)
    return snapshot
