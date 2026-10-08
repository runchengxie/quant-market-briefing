# Weekly Market Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate independently runnable, auditable Chinese weekly market drafts and separately reviewed local publication bundles.

**Architecture:** Add a focused `market_briefing.weekly` package with independent calendar, contracts, context, research, editing and review behavior. Reuse Codex execution, immutable storage primitives and publication-envelope conventions; dispatch explicit weekly commands through the existing CLI without changing daily interfaces.

**Tech Stack:** Python >=3.11,<3.14; existing exchange-calendars, jsonschema, filelock, tzdata, pytest and Ruff; Python tomllib for explicit workspace configuration. No additional runtime dependency.

**Spec:** [Approved design](../specs/2026-10-08-weekly-briefing-design.md).

## Global Constraints

- The first release is a local producer in quant-market-briefing.
- No production schedule or message delivery is introduced by this specification.
- No sibling source imports, directory ownership guesses or automatic copying of shared datasets.
- Source schemas and prompt resources remain packaged under `src/market_briefing/resources/`.
- Runtime artifacts live at <resolved DATA_ROOT>/quant-market-briefing/weekly/<week-start>/rNNNN/.
- Daily paths remain unchanged. Lock by weekly product and week; explicit reruns allocate new revisions.
- Retain consumer ID market-intel. Mechanical checks never grant source approval.
- Principal forecast horizon: one to four weeks. Editorial target: approximately 1,500–2,500 Chinese characters, a soft target.
- Development documentation is English; report text and weekly prompts are natural Chinese.

## Review Focus

- A future scheduled release may be valid evidence even though a realized observation beyond cutoff is invalid: pin in Task 2.
- A hostile or enormous context file must fail before any model invocation, without reading arbitrary linked files: pin in Task 3.
- A resumed editor must reject modified analysis as well as modified evidence, context or resources: pin in Task 5.
- Different futures contracts or price adjustment bases must not produce a plausible-looking weekly return: pin in Task 2.
- Repeated bundle creation or concurrent runs must preserve the existing revision and bundle: pin in Task 6.

## Task 1: Completed-week calendar and external storage

**Files:** Create `src/market_briefing/weekly/__init__.py`, `calendar.py`, `storage.py` and `tests/weekly/test_calendar_storage.py`.

**Interfaces:** `select_week(now: datetime, requested: str = "latest") -> dict` returns status, week_start, week_end_exclusive, retrospective_end, timezone, baseline_session, final_session and scheduled_close; skipped includes reason. `resolve_data_root(explicit: Path | None, settings: Path | None) -> Path` consumes an explicit root or a supplied TOML settings file with data_root; absent both raises an actionable error. `allocate_week(root: Path, week_start: str) -> tuple[Path, int]` wraps existing allocation under root/weekly; caller holds `week_lock(root: Path, week_start: str) -> FileLock`.

- [ ] Write failing tests: latest at Saturday 2026-10-10 00:00 New York selects 2026-10-05; Friday before the 23:59:59 gate selects the previous week; Thursday 2026-11-26 and Friday's early close yield the calendar's actual final session; Good Friday 2026-04-03 yields final session 2026-04-02; DST preserves local midnight boundaries. Reject naive now, non-Monday explicit dates and incomplete explicit weeks. Simulate no sessions and assert skipped/no directory creation. Explicit root overrides TOML, malformed/missing settings fail, repository roots fail, two allocations return r0001/r0002.
- [ ] Run `uv run pytest tests/weekly/test_calendar_storage.py --basetemp D:/data/quant-market-briefing/checks/weekly-task1-red` and confirm failures for missing weekly code.
- [ ] Implement the interfaces using XNYS and ZoneInfo. Clip retrospective_end to min(cutoff, week_end_exclusive); historical reruns retain actual cutoff. Resolve configured data_root then append quant-market-briefing; explicit --data-root already denotes the project root. No hard-coded host paths or change to daily defaults.
- [ ] Run the same tests with a unique task1-green basetemp; all pass.
- [ ] Commit calendar and storage changes with `feat: add weekly calendar and external revision storage`.

## Task 2: Weekly contracts and trustworthy market comparisons

**Files:** Create `weekly/contracts.py`, `weekly/comparisons.py`, `tests/weekly/test_contracts_comparisons.py`, `tests/fixtures/synthetic-week.json`; add `weekly-{evidence,analysis,briefing,review,research,editor}.v1.json` under `resources/schemas/`; extend only the kind allowlist in `contracts.py`.

**Interfaces:** `validate_weekly_document(payload: dict, kind: str) -> None`; `load_weekly_document(path: Path, kind: str) -> dict`; `validate_weekly_analysis(analysis: dict, evidence: dict) -> None`; `calculate_comparison(start: dict, end: dict, method: str) -> dict`. Kinds use the weekly-* resource names. Section topics are exactly `core`, `macro`, `events`, `market_response`, `next_week` in that order.

- [ ] Write failing fixtures/tests: strict schema identity; duplicate IDs; broken references; nonfinite values; mismatched week/cutoff; collection before cutoff; retrospective events outside window; sources/known_at beyond cutoff; scheduled event after cutoff with known_at before cutoff accepted. Null publication timestamps accepted with review warning. Claims require kind fact/inference and evidence_ids; thesis records stance/confidence/horizon=1-4w, drivers/counterevidence/invalidation_conditions. Absent previous report is explicitly absent.
- [ ] Add comparison assertions: 100 to 105 returns 5 percent, 4.0 to 4.1 percent yields 10 basis points; use Decimal and round derived outputs to four decimal places. Reject mismatched instrument/contract/adjustment/unit, nonpositive return baseline and reversed timestamps; retain actual endpoint dates and stale flags. A derived comparison records input IDs/formula/unit and becomes an evidence record before editing.
- [ ] Run `uv run pytest tests/weekly/test_contracts_comparisons.py` with an external unique basetemp; confirm red.
- [ ] Implement schemas with additionalProperties=false, source/observation/event/schedule ID integrity and timezone-aware semantics. Evidence numeric records retain metric/value/unit/reference_period/classification/source_id/observed_at/verification; events retain topic_key, event_at, known_at, evidence_ids and development text; schedules retain event_at/known_at/source_id/status. Analysis stores selected event IDs, comparisons, watchlist IDs and missing inputs. Briefing adds trusted week/run metadata, five named sections with text/claim_ids, brief_text, sources, thesis and quality. Review binds week/run/revision and three document hashes.
- [ ] Run tests and existing `tests/test_contracts.py`; all pass. Commit `feat: define weekly research contracts and comparisons`.

## Task 3: Frozen daily and previous-week context

**Files:** Create `weekly/context.py`, `tests/weekly/test_context.py`.

**Interfaces:** `load_weekly_context(daily_root: Path | None, previous_run: Path | None, week: dict, cutoff: datetime) -> dict`; `freeze_weekly_context(context: dict, run_dir: Path) -> dict` returns inventory hash metadata. Inputs support existing producer daily runs, not arbitrary intel schemas.

- [ ] Write failing tests for missing days, conflicting daily revisions, duplicate source IDs across runs, verified review versus absent/invalid review, previous report week not earlier, cutoff violations and context mutation. Select the highest complete revision per session; missing/incomplete revisions are diagnostics. Previous weekly input must be a validated earlier draft, with audit status separately recorded; reject wrong product, same/later week or future collection. Group event developments by topic_key while retaining distinct dates and corrections.
- [ ] Add resource-boundary tests: maximum 32 daily revisions examined, 2 MiB per JSON and 16 MiB aggregate input; reject files/symlinks resolved outside the supplied context root, unsafe paths and prompt-like data as instructions. Import no credential/config files. Ensure failures precede fake model invocation.
- [ ] Run `uv run pytest tests/weekly/test_context.py` with an external unique basetemp; confirm red.
- [ ] Implement deterministic inventory order, hashes, missing inputs, per-run source namespaces and explicit unreviewed labels. Freeze imported data, never confer approval from an upstream label; verify supplied review hashes before recording reviewed status.
- [ ] Run tests; all pass. Commit `feat: freeze weekly research context and provenance`.

## Task 4: Live weekly research and challenge

**Files:** Create `weekly/research.py`, `resources/prompts/weekly-researcher.zh-CN.md`, `weekly-challenger.zh-CN.md`, `tests/weekly/test_research.py`.

**Interfaces:** `research_week(week: dict, cutoff: datetime, config: dict) -> tuple[dict, dict]` produces weekly evidence and analysis. `reconcile_weekly_revision(initial: dict, candidate: dict) -> tuple[dict, dict]` preserves unchanged identities and remaps changed sources/observations/events/schedules plus dependent references. Reuse execute_stage; do not change daily research logic.

- [ ] Write failing fake-executable tests for full two-live-stage flow, standard one-live-stage override, no completed search, schema failures, timeouts, changed-ID reconciliation and unsupported event/claim references. Assert preserved initial/raw candidate/reconciliation and explicit invocation settings.
- [ ] Run `uv run pytest tests/weekly/test_research.py` with an external unique basetemp; confirm red.
- [ ] Implement analyst/challenge prompts covering five sections, approximately five to ten material events without quotas, surprises only with documented expectations, issuer/official macro originals, attributed conflict claims, counterevidence and verified future calendars. Freeze Python-supplied metadata; validate and compute comparisons before final evidence is frozen. Config defaults retain Astra/xhigh research, Astra/high challenge, 1200 seconds per stage and explicit overrides. Search remains live and required in both stages.
- [ ] Run tests and `tests/test_research.py tests/test_deep_research.py tests/test_deep_failures.py`; all pass. Commit `feat: add weekly live research and counterevidence challenge`.

## Task 5: Chinese editor, validation and runnable weekly commands

**Files:** Create `weekly/editor.py`, `weekly/validate.py`, `weekly/cli.py`, `resources/prompts/weekly-editor.zh-CN.md`, `tests/weekly/test_editor_cli.py`; modify `cli.py` parser and command dispatch; update README and add `docs/weekly-run.md`.

**Interfaces:** `edit_week(analysis: dict, evidence: dict, config: dict) -> dict`; `validate_weekly_draft(evidence: dict, analysis: dict, briefing: dict) -> dict`; `register_commands(commands: argparse._SubParsersAction) -> None`; `dispatch(args: argparse.Namespace, command_prefix: list[str] | None, now: datetime) -> int`. The existing public main(argv, command_prefix, now) remains injectable in tests.

- [ ] Write failing tests for weekly-research/edit/validate CLI, named section order, text consistency, unsupported numbers and unknown claims, estimate qualification, missing category disclosure and 1500–2500-character soft warnings. Assert headings/lists are accepted without using daily BANNED formatting rules; audit stays false and editor search is disabled.
- [ ] Add tests for --workspace-config with no --data-root, explicit override, skipped week, lock contention, retained failure diagnostics and incremental revision IDs. Resumed edit checks evidence/analysis/context/resource hashes, run identity and saved editor model/effort; existing briefing cannot be overwritten. Reject mutation or changed settings and require a fresh research revision. Assert no calls for skipped/invalid inputs.
- [ ] Run `uv run pytest tests/weekly/test_editor_cli.py` with an external unique basetemp; confirm red.
- [ ] Implement four commands including the bundle parser reserved for Task 6; research accepts --week-start latest, optional --daily-context-dir/--previous-weekly-run, --data-root/--workspace-config and current stage settings. Existing-run commands accept --run-dir. Record request/run/failure and resource hashes, use run_id us-weekly-<week-start>-rNNNN, write briefing.json, briefing.txt and validation.json immutably. Resume edit only before any final briefing files exist; if partial output exists, require a fresh revision. Return 0 valid/skipped, 2 failed/invalid. Document actual cutoff and local reviewed-bundle boundary.
- [ ] Run tests plus existing `tests/test_cli.py tests/test_validate.py`; all pass. Commit `feat: generate and validate Chinese weekly drafts`.

## Task 6: Separate source review and local publication bundle

**Files:** Create `weekly/review.py`, `weekly/publication.py`, `tests/weekly/test_publication.py`; connect weekly-bundle dispatch in `weekly/cli.py`; update `docs/integration.md` and `docs/weekly-run.md`.

**Interfaces:** `verify_weekly_review(review: dict, evidence: Path, analysis: Path, briefing: Path) -> None`; `build_weekly_bundle(run_dir: Path, review_path: Path, producer_commit: str, audience: str) -> Path` returns local publication-manifest.json.

- [ ] Write failing tests for approved exact claim set, deferred/rejected/missing/extra decisions, mismatched product/week/run/revision/hash, review before generation, changed stored findings and invalid draft. Every section's referenced claims must be approved. Assert default internal audience, consumer market-intel and weekly schema identifiers.
- [ ] Add repeated/concurrent bundle tests preserving destination, cleanup of only this call's staging directory, fixed relative paths, invalid full commit and audience rejection. Verify unchanged briefing bytes, independent review artifact, no source_audit_passed mutation and no messaging/network calls.
- [ ] Run `uv run pytest tests/weekly/test_publication.py` with an external unique basetemp; confirm red.
- [ ] Implement staged copy/hash/revalidation and atomic publication following the existing envelope. Bundle emits market.weekly-briefing.v1 and market.weekly-source-review.v1; consumers still need explicit weekly adapters.
- [ ] Run tests and existing `tests/test_publication.py`; all pass. Commit `feat: bundle separately reviewed weekly reports`.

## Final validation and handoff

- [ ] Run `uv sync --locked --group dev`, then `uv run pytest --basetemp D:/data/quant-market-briefing/checks/weekly-final-UNIQUE`, `uv run ruff check .`, `uv run ruff format --check .` and `uv build --out-dir D:/data/quant-market-briefing/builds/weekly-UNIQUE`. These paths are resolved examples from local workspace.toml; use the configured roots on another host.
- [ ] Check built wheel contains every weekly schema/prompt. Run installed wheel CLI --help and weekly validation against synthetic external fixtures, not source-tree imports. Run `git diff --check` and review the complete branch for daily compatibility, cutoff semantics and source-review integrity.
- [ ] Manually invoke one real completed-week research run with explicit external root, save timings and source/coverage findings, and inspect originals for representative macro/earnings/calendar claims. Keep it a draft; record errors honestly and repair/revalidate if necessary. No schedule or delivery.
- [ ] Update the PR around implemented behavior, report actual offline/build/live outcomes and remaining consumer/deployment work. Follow workspace merge/cleanup requirements only after required checks pass.

## Plan self-review and execution handoff

Calendar/storage maps to Task 1; contracts/units to Task 2; daily reuse/previous view to Task 3; research/events/challenge to Task 4; Chinese report/CLI to Task 5; review/envelope to Task 6. All five Review Focus conditions have explicit tests. Interface names and contracts are consistent across tasks. No consumer/deployment implementation or historical-vintage claims are included.

Recommended execution: Native, task-by-task in this session, because six tasks share evolving weekly contracts and the first release has no delivery side effects. Request written-plan review and execution-method selection before implementation. A selected Native execution uses executing-plans; independent branch review follows its workflow. Subagent-driven remains an available user-selected alternative.
