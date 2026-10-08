"""Weekly command orchestration; no production or message side effects."""

import argparse
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from ..review import file_hash
from ..storage import assert_external_path, write_atomic
from .calendar import select_week
from .context import freeze_weekly_context, load_weekly_context
from .contracts import load_weekly_document
from .editor import edit_week
from .storage import allocate_week, resolve_data_root, week_lock
from .validate import validate_weekly_draft


def register_commands(commands: argparse._SubParsersAction) -> None:
    research = commands.add_parser(
        "weekly-research", help="Live research for a completed New York week"
    )
    research.add_argument("--week-start", default="latest")
    research.add_argument("--data-root", type=Path)
    research.add_argument("--workspace-config", type=Path)
    research.add_argument("--daily-context-dir", type=Path)
    research.add_argument("--previous-weekly-run", type=Path)
    research.add_argument("--research-depth", choices=["standard", "deep"], default="deep")
    efforts = ["low", "medium", "high", "xhigh", "max"]
    for stage, model, effort in [
        ("analyst", "gpt-6-astra", "xhigh"),
        ("reviewer", "gpt-6-astra", "high"),
        ("editor", "gpt-6.1-sol", "medium"),
    ]:
        research.add_argument(f"--{stage}-model", default=model)
        research.add_argument(f"--{stage}-effort", choices=efforts, default=effort)
    research.add_argument("--timeout-seconds", type=float, default=1200)
    for command in ["weekly-edit", "weekly-validate", "weekly-bundle"]:
        parser = commands.add_parser(command)
        parser.add_argument("--run-dir", type=Path, required=True)
        if command == "weekly-edit":
            parser.add_argument("--editor-model")
            parser.add_argument("--editor-effort", choices=efforts)
            parser.add_argument("--timeout-seconds", type=float, default=1200)
        if command == "weekly-bundle":
            parser.add_argument("--review", type=Path, required=True)
            parser.add_argument("--producer-commit", required=True)
            parser.add_argument("--audience", choices=["internal", "public"], default="internal")


def _emit(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _text_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _finish(evidence: dict, analysis: dict, config: dict) -> int:
    run = config["run_dir"]
    if any((run / name).exists() for name in ["briefing.json", "briefing.txt", "validation.json"]):
        raise ValueError("Final output already exists; create a fresh research revision")
    brief = edit_week(analysis, evidence, config)
    write_atomic(run / "briefing.json", brief)
    _text_atomic(run / "briefing.txt", brief["headline"] + "\n\n" + brief["brief_text"] + "\n")
    write_atomic(run / "validation.json", brief["quality"])
    _emit(
        {
            "status": brief["status"],
            "run_dir": str(run),
            "briefing": str(run / "briefing.json"),
            "quality": brief["quality"],
        }
    )
    return 0 if not brief["quality"]["errors"] else 2


def dispatch(args: argparse.Namespace, command_prefix: list[str] | None, now: datetime) -> int:
    from ..cli import resource_hashes
    from .research import research_week

    if args.command == "weekly-research":
        root = resolve_data_root(args.data_root, args.workspace_config)
        week = select_week(now, args.week_start)
        if week["status"] == "skipped":
            _emit(week)
            return 0
        if args.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        context = load_weekly_context(args.daily_context_dir, args.previous_weekly_run, week, now)
        with week_lock(root, week["week_start"]):
            run, revision = allocate_week(root, week["week_start"])
            config = {
                "run_dir": run,
                "run_id": f"us-weekly-{week['week_start']}-r{revision:04d}",
                "revision": revision,
                "command_prefix": command_prefix,
                "weekly_context": context,
                "timeout_seconds": args.timeout_seconds,
                "research_depth": args.research_depth,
                **{
                    f"{stage}_{field}": getattr(args, f"{stage}_{field}")
                    for stage in ["analyst", "reviewer", "editor"]
                    for field in ["model", "effort"]
                },
            }
            context_metadata = freeze_weekly_context(context, run)
            metadata = {
                "schema_version": "market.weekly-run.v1",
                "product": "weekly",
                "week_start": week["week_start"],
                "run_id": config["run_id"],
                "revision": revision,
                "evidence_cutoff": now.isoformat(),
                "requested_at": now.isoformat(),
                "resource_hashes": resource_hashes(),
                **context_metadata,
                **{
                    key: value
                    for key, value in config.items()
                    if key not in {"run_dir", "command_prefix", "weekly_context"}
                },
            }
            write_atomic(run / "request.json", metadata)
            try:
                evidence, analysis = research_week(week, now, config)
                write_atomic(run / "evidence.json", evidence)
                write_atomic(run / "analysis.json", analysis)
                metadata.update(
                    evidence_sha256=file_hash(run / "evidence.json"),
                    analysis_sha256=file_hash(run / "analysis.json"),
                )
                write_atomic(run / "run.json", metadata)
                return _finish(evidence, analysis, config)
            except (ValueError, RuntimeError, OSError) as exc:
                write_atomic(run / "failure.json", {"status": "failed", "error": str(exc)})
                raise
    run = assert_external_path(args.run_dir)
    evidence = load_weekly_document(run / "evidence.json", "weekly-evidence")
    with week_lock(run.parent.parent.parent, evidence["week_start"]):
        analysis = load_weekly_document(run / "analysis.json", "weekly-analysis")
        metadata = json.loads((run / "run.json").read_text(encoding="utf-8"))
        expected_id = f"us-weekly-{evidence['week_start']}-r{metadata['revision']:04d}"
        if (
            metadata["product"] != "weekly"
            or metadata["run_id"] != expected_id
            or metadata["week_start"] != evidence["week_start"]
        ):
            raise ValueError("Weekly run identity mismatch")
        for name, field in [
            ("evidence", "evidence_sha256"),
            ("analysis", "analysis_sha256"),
            ("weekly-context", "context_sha256"),
        ]:
            if file_hash(run / f"{name}.json") != metadata[field]:
                raise ValueError(f"Frozen {name} changed; create a new revision")
        if metadata["resource_hashes"] != resource_hashes():
            raise ValueError("Prompts/schemas changed; create a new revision")
        if args.command == "weekly-edit":
            for field in ["editor_model", "editor_effort"]:
                override = getattr(args, field)
                if override is not None and override != metadata[field]:
                    raise ValueError("Changed editor settings require a new revision")
            config = {
                **metadata,
                "run_dir": run,
                "command_prefix": command_prefix,
                "timeout_seconds": args.timeout_seconds,
            }
            return _finish(evidence, analysis, config)
        if args.command == "weekly-validate":
            brief = load_weekly_document(run / "briefing.json", "weekly-briefing")
            quality = validate_weekly_draft(evidence, analysis, brief)
            _emit(quality)
            return 0 if not quality["errors"] else 2
        from .publication import build_weekly_bundle

        manifest = build_weekly_bundle(run, args.review, args.producer_commit, args.audience)
        _emit({"status": "reviewed_bundle", "manifest": str(manifest)})
        return 0
