"""Local file producer. This command never delivers messages."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from filelock import Timeout

from .analysis import analyze
from .calendar import select_session
from .context import load_context
from .contracts import aware_time, load_document
from .editor import edit
from .publication import build_bundle
from .research import research
from .review import file_hash
from .storage import allocate_revision, assert_external_path, date_lock, write_atomic
from .validate import validate_draft


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Web-research and frozen-evidence U.S. market briefing producer"
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name in ["run", "analyze", "research"]:
        command = commands.add_parser(name)
        command.add_argument(
            "--date", default="today", help="ISO session date, today, or latest completed session"
        )
        if name != "research":
            command.add_argument("--evidence", type=Path, required=True)
        else:
            command.add_argument(
                "--context", type=Path, help="Existing intel research JSON; unreviewed search leads"
            )
        command.add_argument(
            "--data-root", type=Path, default=Path.home() / "data" / "quant-market-briefing"
        )
        command.add_argument("--analyst-model", default="gpt-6-astra")
        command.add_argument(
            "--analyst-effort", choices=["low", "medium", "high", "xhigh", "max"], default="xhigh"
        )
        command.add_argument("--reviewer-model", default="gpt-6-astra")
        command.add_argument(
            "--reviewer-effort", choices=["low", "medium", "high", "xhigh", "max"], default="high"
        )
        command.add_argument("--editor-model", default="gpt-6.1-sol")
        command.add_argument(
            "--editor-effort", choices=["low", "medium", "high", "xhigh", "max"], default="medium"
        )
        command.add_argument("--research-depth", choices=["standard", "deep"], default="deep")
        command.add_argument("--timeout-seconds", type=float, default=1200)
    edit_command = commands.add_parser("edit")
    edit_command.add_argument("--run-dir", type=Path, required=True)
    edit_command.add_argument("--editor-model")
    edit_command.add_argument("--editor-effort", choices=["low", "medium", "high", "xhigh", "max"])
    edit_command.add_argument("--timeout-seconds", type=float, default=600)
    validate = commands.add_parser("validate")
    validate.add_argument("--run-dir", type=Path, required=True)
    bundle = commands.add_parser("bundle")
    bundle.add_argument("--run-dir", type=Path, required=True)
    bundle.add_argument("--review", type=Path, required=True)
    bundle.add_argument("--producer-commit", required=True)
    bundle.add_argument("--audience", choices=["internal", "public"], default="internal")
    return root


def _print(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))


def resource_hashes() -> dict:
    resource_root = Path(str(files("market_briefing").joinpath("resources")))
    return {
        path.relative_to(resource_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in resource_root.rglob("*")
        if path.is_file()
    }


def _config(args, run_dir: Path, revision: int, market_date: str, command_prefix) -> dict:
    return {
        "run_dir": run_dir,
        "revision": revision,
        "run_id": f"us-{market_date}-r{revision:04d}",
        "analyst_model": getattr(args, "analyst_model", None),
        "editor_model": getattr(args, "editor_model", None),
        "analyst_effort": getattr(args, "analyst_effort", None),
        "reviewer_model": getattr(args, "reviewer_model", None),
        "reviewer_effort": getattr(args, "reviewer_effort", None),
        "editor_effort": getattr(args, "editor_effort", None),
        "research_depth": getattr(args, "research_depth", "standard"),
        "timeout_seconds": args.timeout_seconds,
        "command_prefix": command_prefix,
    }


def _finish_editor(evidence: dict, analysis: dict, config: dict) -> int:
    brief = edit(analysis, evidence, config)
    write_atomic(config["run_dir"] / "briefing.json", brief)
    _print(
        {
            "status": brief["status"],
            "run_dir": str(config["run_dir"]),
            "briefing": str(config["run_dir"] / "briefing.json"),
            "quality": brief["quality"],
        }
    )
    return 0 if not brief["quality"]["errors"] else 2


def _generate(args, command_prefix, now: datetime) -> int:
    args.data_root = assert_external_path(args.data_root)
    session = select_session(now, None if args.date == "today" else args.date)
    if session["status"] == "skipped":
        _print(session)
        return 0
    evidence = None
    if args.command != "research":
        evidence = load_document(args.evidence, "evidence")
        if evidence["market_date"] != session["market_date"]:
            raise ValueError("Evidence does not match selected session")
        if aware_time(evidence["scheduled_close"]) != aware_time(session["scheduled_close"]):
            raise ValueError("Evidence close does not match exchange calendar")
        if aware_time(evidence["collected_at"]) > now:
            raise ValueError("Evidence collection timestamp is in the future")
    if args.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    imported_context = None
    if getattr(args, "context", None) is not None:
        imported_context = load_context(args.context, session, now)
    with date_lock(args.data_root, session["market_date"]):
        run_dir, revision = allocate_revision(args.data_root, session["market_date"])
        config = _config(args, run_dir, revision, session["market_date"], command_prefix)
        if imported_context is not None:
            write_atomic(run_dir / "research-context.json", imported_context)
            config["research_context"] = imported_context
        context_metadata = (
            {
                "research_context_sha256": file_hash(run_dir / "research-context.json"),
                "research_context_source_sha256": imported_context["source_sha256"],
            }
            if imported_context is not None
            else {}
        )
        write_atomic(
            run_dir / "request.json",
            {
                "market_date": session["market_date"],
                "requested_at": now.isoformat(),
                "evidence_cutoff": now.isoformat()
                if args.command == "research"
                else evidence["evidence_cutoff"],
                "input_mode": "web_research" if args.command == "research" else "frozen_evidence",
                "resource_hashes": resource_hashes(),
                "analyst_model": config["analyst_model"],
                "editor_model": config["editor_model"],
                **context_metadata,
                **{
                    k: config[k]
                    for k in (
                        "analyst_effort",
                        "reviewer_model",
                        "reviewer_effort",
                        "editor_effort",
                        "research_depth",
                    )
                },
            },
        )
        try:
            if args.command == "research":
                evidence, analysis = research(session, now, config)
            else:
                write_atomic(run_dir / "evidence.json", evidence)
                analysis = analyze(evidence, config)
            if args.command == "research":
                write_atomic(run_dir / "evidence.json", evidence)
        except (ValueError, RuntimeError, OSError) as exc:
            write_atomic(run_dir / "failure.json", {"status": "failed", "error": str(exc)})
            raise
        fingerprint = {
            "schema_version": "market.run.v1",
            "run_id": config["run_id"],
            "revision": revision,
            "market_date": session["market_date"],
            "replay": session["replay"],
            "input_mode": "web_research" if args.command == "research" else "frozen_evidence",
            "evidence_sha256": file_hash(run_dir / "evidence.json"),
            "analyst_model": config["analyst_model"],
            "editor_model": config["editor_model"],
            **context_metadata,
            **{
                k: config[k]
                for k in (
                    "analyst_effort",
                    "reviewer_model",
                    "reviewer_effort",
                    "editor_effort",
                    "research_depth",
                )
            },
            "resource_hashes": resource_hashes(),
        }
        write_atomic(run_dir / "run.json", fingerprint)
        try:
            write_atomic(run_dir / "analysis.json", analysis)
            if args.command == "analyze":
                _print({"status": "analysis_ready", "run_dir": str(run_dir)})
                return 0
            return _finish_editor(evidence, analysis, config)
        except (ValueError, RuntimeError, OSError) as exc:
            write_atomic(run_dir / "failure.json", {"status": "failed", "error": str(exc)})
            raise


def _existing(args, command_prefix) -> int:
    run_dir = assert_external_path(args.run_dir)
    evidence = load_document(run_dir / "evidence.json", "evidence")
    with date_lock(run_dir.parent.parent, evidence["market_date"]):
        analysis = load_document(run_dir / "analysis.json", "analysis")
        if args.command == "edit":
            metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            if file_hash(run_dir / "evidence.json") != metadata["evidence_sha256"]:
                raise ValueError("Frozen evidence changed after analysis")
            if (
                metadata.get("research_context_sha256")
                and file_hash(run_dir / "research-context.json")
                != metadata["research_context_sha256"]
            ):
                raise ValueError("Frozen research context changed after analysis")
            if metadata["resource_hashes"] != resource_hashes():
                raise ValueError("Prompts/schemas changed; create a new run revision")
            saved_model = metadata["editor_model"]
            if args.editor_model is not None and args.editor_model != saved_model:
                raise ValueError("Changed editor model requires a new run revision")
            args.editor_model = saved_model
            saved_effort = metadata.get("editor_effort")
            if args.editor_effort is not None and args.editor_effort != saved_effort:
                raise ValueError("Changed editor effort requires a new run revision")
            args.editor_effort = saved_effort
            config = _config(
                args, run_dir, metadata["revision"], evidence["market_date"], command_prefix
            )
            if config["run_id"] != metadata["run_id"]:
                raise ValueError("Run identity mismatch")
            return _finish_editor(evidence, analysis, config)
        if args.command == "validate":
            brief = load_document(run_dir / "briefing.json", "briefing")
            quality = validate_draft(evidence, analysis, brief)
            _print(quality)
            return 0 if not quality["errors"] else 2
        manifest = build_bundle(run_dir, args.review, args.producer_commit, args.audience)
        _print({"status": "reviewed_bundle", "manifest": str(manifest)})
        return 0


def main(
    argv: list[str] | None = None,
    *,
    command_prefix: list[str] | None = None,
    now: datetime | None = None,
) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in {"run", "analyze", "research"}:
            return _generate(args, command_prefix, now or datetime.now(UTC))
        return _existing(args, command_prefix)
    except (ValueError, RuntimeError, OSError, Timeout) as exc:
        print(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
