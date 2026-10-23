"""Self-contained research sidecars bound to reviewed briefing bytes."""

import re
from pathlib import Path

from .artifacts import raw_digest, read_bounded
from .numeric_bindings import digest
from .research_state import build_continuity, validate_state
from .storage import write_atomic

NAME = "research-audit.json"
MARKER = "Research audit SHA256: "
MEMBERS = {
    "prior-inventory.json",
    "research-state.json",
    "continuity.json",
    "comparison-input.json",
    "comparisons.json",
    "research-questions.json",
}


def member_name(name: str) -> bool:
    return name in MEMBERS or bool(re.fullmatch(r"research-attempt-000[0-3]\.json", name))


def audit_marker(record: dict) -> str:
    return MARKER + digest(record)


def write_audit(run_dir: Path, members: dict[str, dict]) -> dict:
    evidence, _ = read_bounded(run_dir / "evidence.json", run_dir)
    analysis, _ = read_bounded(run_dir / "analysis.json", run_dir)
    for name, doc in members.items():
        if not member_name(name):
            raise ValueError("Unexpected audit member")
        path = run_dir / name
        if path.exists():
            if read_bounded(path, run_dir)[0] != doc:
                raise ValueError("Audit member already differs")
        else:
            write_atomic(path, doc)
    record = {
        "schema_version": "market.research-audit.v1",
        "evidence_sha256": digest(evidence),
        "analysis_sha256": digest(analysis),
        "members": {
            name: {"sha256": digest(doc), "document": doc} for name, doc in members.items()
        },
    }
    write_atomic(run_dir / NAME, record)
    return record


def verify_record(record: dict, briefing: dict, evidence: dict, analysis: dict) -> None:
    from .contracts import validate_document

    validate_document(record, "research-audit")
    if (record["evidence_sha256"], record["analysis_sha256"]) != (
        digest(evidence),
        digest(analysis),
    ):
        raise ValueError("Research audit inputs changed")
    members = record["members"]
    if not {"prior-inventory.json", "research-state.json", "continuity.json"} <= members.keys():
        raise ValueError("Missing required research audit member")
    for name, item in members.items():
        if not member_name(name) or digest(item["document"]) != item["sha256"]:
            raise ValueError("Invalid research audit member")
    docs = {name: item["document"] for name, item in members.items()}
    prior = docs["prior-inventory.json"]
    state = docs["research-state.json"]
    if "comparison-input.json" in docs or "comparisons.json" in docs:
        from .comparisons import (
            calculate_comparisons,
            merge_comparisons,
            validate_comparison_claims,
        )

        calculated = calculate_comparisons(
            docs["comparison-input.json"], evidence["evidence_cutoff"]
        )
        if (
            calculated != docs["comparisons.json"]
            or merge_comparisons(evidence, calculated) != evidence
        ):
            raise ValueError("Derived research evidence changed")
        validate_comparison_claims(analysis, calculated)
    validate_state(state, analysis, evidence, prior)
    if docs["continuity.json"] != build_continuity(prior, state):
        raise ValueError("Changed research continuity")
    if audit_marker(record) not in briefing["quality"]["warnings"]:
        raise ValueError("Research audit marker is missing or changed")


def load_audit(run_dir: Path) -> dict | None:
    path = run_dir / NAME
    return read_bounded(path, run_dir)[0] if path.exists() else None


def verify_audit(run_dir: Path, briefing: dict, evidence: dict, analysis: dict) -> None:
    record = load_audit(run_dir)
    if record is None:
        if any(w.startswith(MARKER) for w in briefing["quality"]["warnings"]):
            raise ValueError("Missing research audit")
        return
    verify_record(record, briefing, evidence, analysis)
    for name, item in record["members"].items():
        if read_bounded(run_dir / name, run_dir)[0] != item["document"]:
            raise ValueError("Research sidecar changed")
    prior = record["members"]["prior-inventory.json"]["document"]
    from .prior import INPUTS

    for item in prior["inventory"]:
        name = item["name"]
        if name not in {f"{k}.json" for k in INPUTS}:
            raise ValueError("Unexpected prior input member")
        doc, raw = read_bounded(run_dir / "prior-inputs" / name, run_dir)
        if len(raw) != item["bytes"] or raw_digest(raw) != item["sha256"]:
            raise ValueError("Frozen prior bytes changed")
        key = name.removesuffix(".json")
        if key in prior["documents"] and doc != prior["documents"][key]:
            raise ValueError("Prior summary differs from frozen input")


def copy_supporting(source: Path, destination: Path) -> None:
    record = load_audit(source)
    if record is None:
        return
    from .prior import INPUTS

    names = [NAME, *record["members"]]
    if any(not member_name(name) for name in record["members"]):
        raise ValueError("Unsafe audit member")
    for item in record["members"]["prior-inventory.json"]["document"]["inventory"]:
        if item["name"] not in {f"{name}.json" for name in INPUTS}:
            raise ValueError("Unsafe prior member")
        names.append("prior-inputs/" + item["name"])
    for name in names:
        _, raw = read_bounded(source / name, source)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
