"""Bounded, frozen producer artifacts used only as research leads."""

import copy
import json
import re
from datetime import datetime
from pathlib import Path

import exchange_calendars as xcals

from ..analysis import validate_analysis
from ..contracts import aware_time, validate_document
from ..review import file_hash, verify_review
from ..storage import write_atomic
from .contracts import validate_weekly_analysis, validate_weekly_document


def load_weekly_context(
    daily_root: Path | None, previous_run: Path | None, week: dict, cutoff: datetime
) -> dict:
    budget = 0
    inventory = []

    def read(path: Path, owner: Path) -> dict:
        nonlocal budget
        resolved = path.resolve()
        if not resolved.is_relative_to(owner.resolve()) or path.is_symlink():
            raise ValueError("Context file escapes supplied root")
        size = path.stat().st_size
        budget += size
        if size > 2 * 1024 * 1024 or budget > 16 * 1024 * 1024:
            raise ValueError("Context size limit exceeded")
        raw = path.read_bytes()
        if len(raw) != size:
            raise ValueError("Context changed while reading")

        def reject(value):
            raise ValueError(f"Invalid JSON constant {value}")

        doc = json.loads(raw.decode("utf-8"), parse_constant=reject)
        import hashlib

        inventory.append(
            {"path": str(resolved), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": size}
        )
        return doc

    result = {
        "daily_runs": [],
        "previous_view": {
            "status": "absent",
            "week_start": None,
            "sha256": None,
            "comparison": "无上周报告可比较。",
            "audit_status": "unreviewed",
            "briefing": None,
        },
        "missing_inputs": [],
        "inventory": inventory,
    }
    if daily_root is not None:
        root = daily_root.resolve()
        if not root.is_dir():
            raise ValueError("Daily context root does not exist")
        calendar = xcals.get_calendar(
            "XNYS",
            start=f"{int(week['week_start'][:4]) - 1}-01-01",
            end=f"{int(week['week_start'][:4]) + 1}-12-31",
        )
        count = 0
        for session in calendar.sessions_in_range(week["week_start"], week["final_session"]):
            day = session.date().isoformat()
            parent = root / day
            if parent.is_symlink():
                raise ValueError("Context session cannot be a symlink")
            candidates = (
                sorted(
                    [p for p in parent.iterdir() if re.fullmatch(r"r\d{4,}", p.name)],
                    key=lambda p: int(p.name[1:]),
                    reverse=True,
                )
                if parent.exists()
                else []
            )
            count += len(candidates)
            if count > 32:
                raise ValueError("Context revision limit exceeded")
            chosen = None
            for run in candidates:
                if run.is_symlink():
                    raise ValueError("Context revision cannot be a symlink")
                if all(
                    (run / f"{name}.json").is_file()
                    for name in ["evidence", "analysis", "briefing"]
                ):
                    chosen = run
                    break
                result["missing_inputs"].append(f"Incomplete daily revision: {day}/{run.name}")
            if chosen is None:
                result["missing_inputs"].append(f"Missing daily session: {day}")
                continue
            docs = {
                name: read(chosen / f"{name}.json", root)
                for name in ["evidence", "analysis", "briefing"]
            }
            for name, doc in docs.items():
                validate_document(doc, name)
            evidence = docs["evidence"]
            validate_analysis(docs["analysis"], evidence)
            if evidence["market_date"] != day or docs["briefing"]["market_date"] != day:
                raise ValueError("Daily context session mismatch")
            if any(
                aware_time(evidence[key]) > cutoff for key in ["evidence_cutoff", "collected_at"]
            ):
                raise ValueError("Daily context is after weekly cutoff")
            audit = "unreviewed"
            if (chosen / "review.json").exists():
                review = read(chosen / "review.json", root)
                verify_review(
                    review,
                    *(chosen / f"{name}.json" for name in ["evidence", "analysis", "briefing"]),
                )
                if aware_time(review["reviewed_at"]) > cutoff:
                    raise ValueError("Daily review is after cutoff")
                audit = "reviewed"
            prefix = f"daily_{day}_{chosen.name}_"
            evidence = copy.deepcopy(evidence)
            for source in evidence["sources"]:
                source["id"] = prefix + source["id"]
            for observation in evidence["observations"]:
                observation["id"] = prefix + observation["id"]
                observation["source_id"] = prefix + observation["source_id"]
            result["daily_runs"].append(
                {
                    "market_date": day,
                    "revision": chosen.name,
                    "audit_status": audit,
                    "evidence": evidence,
                    "previous_interpretation": docs["briefing"]["brief_text"],
                }
            )
    else:
        result["missing_inputs"].append("Daily context was not supplied; use live research.")
    if previous_run is not None:
        root = previous_run.resolve()
        docs = {
            name: read(root / f"{name}.json", root) for name in ["evidence", "analysis", "briefing"]
        }
        for name, doc in docs.items():
            validate_weekly_document(doc, f"weekly-{name}")
        validate_weekly_analysis(docs["analysis"], docs["evidence"])
        brief = docs["briefing"]
        from .validate import validate_weekly_draft

        quality = validate_weekly_draft(docs["evidence"], docs["analysis"], brief)
        if quality["errors"] or quality != brief["quality"]:
            raise ValueError("Previous weekly draft has invalid or changed findings")
        if brief["status"] != "validated_draft" or brief["week_start"] >= week["week_start"]:
            raise ValueError("Previous weekly draft must be validated and earlier")
        if (
            aware_time(brief["generated_at"]) > cutoff
            or aware_time(docs["evidence"]["collected_at"]) > cutoff
        ):
            raise ValueError("Previous weekly context after cutoff")
        audit = "unreviewed"
        if (root / "review.json").exists():
            from .review import verify_weekly_review

            review = read(root / "review.json", root)
            verify_weekly_review(
                review, *(root / f"{name}.json" for name in ["evidence", "analysis", "briefing"])
            )
            if aware_time(review["reviewed_at"]) > cutoff:
                raise ValueError("Previous review after cutoff")
            audit = "reviewed"
        result["previous_view"] = {
            "status": "available",
            "week_start": brief["week_start"],
            "sha256": next(
                item["sha256"]
                for item in reversed(inventory)
                if item["path"] == str((root / "briefing.json").resolve())
            ),
            "audit_status": audit,
            "briefing": brief,
            "comparison": "Previous interpretation; reassess from originals.",
        }
    return result


def freeze_weekly_context(context: dict, run_dir: Path) -> dict:
    write_atomic(run_dir / "weekly-context.json", context)
    return {"context_sha256": file_hash(run_dir / "weekly-context.json")}
