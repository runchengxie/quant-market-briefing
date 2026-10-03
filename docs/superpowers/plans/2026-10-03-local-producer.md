# Quant Market Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after review. Steps use checkbox syntax for tracking. Execution recommendation: native implementation in this session; no parallel implementation required.

**Goal:** Build a standalone local producer that converts frozen U.S. market evidence into a traceable five-paragraph Chinese draft and a reviewed publication bundle.

**Architecture:** Two separate Codex subprocess stages read immutable evidence and analysis. Deterministic Python code owns metadata, validation, revision directories and publication hashes. Existing intel and deployment owners remain responsible for rendering and scheduling.

**Tech Stack:** Python 3.11–3.13, uv, argparse, jsonschema, exchange-calendars, filelock, Codex CLI; pytest for focused implementation tests after approval.

**Spec:** [Design](../specs/2026-10-03-local-producer-design.md).

## Global Constraints

- Stage 1 applies the user's fundamental/macro research template; Stage 2 produces exactly five natural Chinese paragraphs.
- No imports from sibling business source trees. No strategy/backtest dependency.
- Runtime outputs default to ~/data/quant-market-briefing; credentials remain outside source control.
- Publication consumer ID remains `market-intel`; current repository name is `quant-intel-platform`.
- Structural validation is not source approval. Review binds evidence, analysis and briefing hashes.
- Production activation and real delivery are separate from this local producer release.

## Review Focus

- Monthly macro and weekly earnings estimates must retain original periods instead of being presented as same-day actuals (Task 1).
- An interrupted model process must not leave a successful stage or publishable partial file (Task 2).
- Fluent editing must not add unsupported numbers or strengthen causal claims (Task 3).
- An edit after source approval must invalidate the reviewed bundle (Task 4).
- A holiday, early close or replay must not select an unfinished session or silently redeliver an old report (Task 5).

## Task 1: Evidence and output contracts

**Files:** `pyproject.toml`, `AGENTS.md`, `README.md`, `schemas/{evidence,analysis,briefing}.v1.json`, `src/market_briefing/{__init__,contracts}.py`, `tests/test_contracts.py`, `tests/fixtures/synthetic-session.json`.

**Interfaces:** `load_document(path: Path, kind: str) -> dict`; `validate_document(payload: dict, kind: str) -> None`. Evidence observations use ID, value, unit, reference period, actual/estimate classification, source ID, observation/publication times and verification state. Unknown fields are rejected. Trusted run metadata is separate from model output schemas.

- [x] Create an independent repository on a task branch; record scope and external data-root rules in AGENTS.md.
- [x] Write failing tests for unknown fields, naive timestamps, wrong units, duplicate evidence IDs, unresolved source IDs, and estimates presented without a reference period.
- [x] Implement JSON Schema and cross-field validation, package schema resources, and synthetic fixtures without real market/provider data.
- [x] Run `uv run pytest tests/test_contracts.py`; confirm these cases pass, then commit.

## Task 2: Analyst execution

**Files:** `src/market_briefing/{codex,analysis}.py`, `prompts/analyst.md`, `tests/test_codex.py`, `tests/test_analysis.py`.

**Interfaces:** `execute_stage(prompt: str, schema: Path, output: Path, model: str | None, timeout_seconds: int, cwd: Path) -> dict`; `analyze(evidence: dict, config: dict) -> dict`.

- [x] Write failing tests using a fake executable for valid output, nonzero exit, timeout, invalid JSON, missing output and partial output. Tests invoke no paid model.
- [x] Implement argument-array subprocess invocation with UTF-8 stdin, explicit working directory, ephemeral execution, structured final output and separate event/error logs.
- [x] Add the user's complete analytical structure to analyst.md, including supporting/contrary evidence, causal uncertainty, missing-data handling and distinction between quarterly growth and forward returns.
- [x] Validate evidence references in analysis. Make model choice configurable. Retry transient process errors at most twice; do not retry deterministic validation errors automatically.
- [x] Run the two targeted test files and commit.

## Task 3: Chinese editor and draft validation

**Files:** `src/market_briefing/{editor,validate}.py`, `prompts/editor.zh-CN.md`, `tests/test_editor.py`, `tests/test_validate.py`.

**Interfaces:** `edit(analysis: dict, evidence: dict, config: dict) -> dict`; `validate_draft(evidence: dict, analysis: dict, briefing: dict) -> dict`.

- [x] Write failing tests for paragraph counts, unsupported numeric claims, changed forecast/actual classification, dangling claim references, Markdown, lists, emoji, quotation marks, semicolons and dashes.
- [x] Implement exactly five paragraph objects with claim/evidence links; Python derives brief_text using two newlines and supplies date/run metadata.
- [x] Encode natural Chinese rules and a soft 800–1,200-character target. Treat unfamiliar English prose and formulaic contrast as editorial warnings requiring review, not mechanical proof of poor research.
- [x] Return individual structural/evidence-link/editorial findings. Preserve draft status even when deterministic checks pass; semantic faithfulness remains independently reviewed.
- [x] Run targeted tests and commit.

## Task 4: Immutable runs and reviewed publication bundles

**Files:** `src/market_briefing/{storage,review,publication}.py`, `schemas/source-review.v1.json`, `tests/test_storage.py`, `tests/test_publication.py`.

**Interfaces:** `write_atomic(path: Path, payload: dict) -> None`; `verify_review(review: dict, evidence: Path, analysis: Path, briefing: Path) -> None`; `build_bundle(run_dir: Path, review_path: Path, producer_commit: str, audience: str) -> Path`.

- [x] Write failing tests for concurrent locks, changed hashes, unhandled/deferred/rejected final claims, unsafe relative paths, missing commit identity and attempted overwrite of approved revisions.
- [x] Implement per-date filelock, immutable revision directories, canonical UTF-8 JSON and atomic stage writes. Cache only when evidence/prompt/schema/model hashes all match. Never update latest on failure.
- [x] Implement hash-bound source-review records. A bundle requires every final claim to be approved; missing/deferred optional material must be removed through a new draft revision and re-reviewed.
- [x] Emit `research.platform-publication.v1` with existing exact field names and consumer `market-intel`. Default audience to internal. Bundle creation only writes local artifacts.
- [x] Run targeted tests and commit.

## Task 5: CLI, exchange session selection and operational handoff

**Files:** `src/market_briefing/{calendar,cli}.py`, `tests/test_calendar.py`, `tests/test_cli.py`, `docs/local-run.md`, `docs/integration.md`.

**Interfaces:** CLI `market-briefing analyze|edit|validate|bundle|run`; explicit `--date`, `--evidence`, `--data-root`, stage model and timeout settings. `select_session(now: datetime, requested_date: str | None) -> dict` uses XNYS calendar and America/New_York.

- [x] Write failing tests for ordinary close, holiday skip, daylight saving time, early close, pre-close rejection, explicit historical replay and rerun revision identity.
- [x] Implement local commands, readiness/error exit codes and skipped-session records. Validate collection cutoff without claiming replayed evidence is a historical vintage.
- [x] Document a frozen-evidence local run and hash-bound review workflow. Do not install any scheduler or trigger notifications.
- [x] Run focused tests plus the new project's offline quality gates, inspect a synthetic final bundle, and prepare a reviewable commit/PR according to the new repository's chosen visibility and remote setup.

## Separate follow-up plans

The first release accepts an evidence file. Intel context export, the `market.briefing.v1` renderer/import adapter, independent review automation and deployment scheduling require follow-up plans based on the actual consumer interfaces. The generic publication verifier alone does not implement a briefing renderer.

## Current progress and handoff

Tasks 1–5 were implemented locally on feat/local-producer-root. All 68 offline tests passed, Ruff passed, the wheel built, installed wheel resources were checked, and the existing publication contract accepted the synthetic internal bundle while rejecting public disclosure. Independent review findings were fixed with regression tests. Stage caching was deferred in favor of new immutable revisions. GitHub publication awaits a visibility choice. No real Codex generation, production schedule or message delivery was performed. Core intel naming documentation merged separately through PR #188.
