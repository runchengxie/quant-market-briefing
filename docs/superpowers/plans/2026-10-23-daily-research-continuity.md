# Daily Research Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add auditable daily research continuity, comparable historical calculations, evidence acceptance and frozen-input evaluation to the local briefing producer.

**Architecture:** Four increments share immutable input inventories and a research-audit digest. Structured internal model output projects onto the existing public daily evidence/analysis/briefing contracts; previous interpretations never become current evidence automatically. Evaluation is a separate local command and cannot publish artifacts or relax production gates.

**Tech Stack:** Python 3.11–3.13, existing jsonschema/Decimal/FastAPI-free CLI stack, pytest, Ruff, uv/hatchling; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-23-daily-research-continuity-design.md` (approved 2026-10-23).

## Global Constraints

- Preserve natural Chinese five-paragraph daily output and independent source approval.
- No trading signals, frontend, delivery, schedules or production configuration.
- Producer must not import sibling source; owner data comes through explicit versioned files.
- Published `market.briefing.v1` and consumer ID `market-intel` remain unchanged.
- Keep `source_audit_passed=false`; mechanical acceptance cannot grant approval.
- Runtime inputs/results live under explicit external paths; all writes are immutable and never update shared latest pointers.
- Missing assessment is not neutral; missing evidence is not zero or negative evidence.
- New structured runs cannot silently fall back to legacy behavior or drop sidecars during retry/resumption.
- Run focused and full offline tests, Ruff, package builds and independent review before integration; no paid models in tests or CI.
- Existing standing authorization governs PR merge, merged-result verification and task-only cleanup.

## Review Focus

1. Prior artifact generated after the current cutoff: reject it even if its market date is earlier (Task 1).
2. Legacy prior without structured short-term state: show unavailable rather than infer sentiment (Task 1).
3. Same numeric levels with different instrument/basis/provider: refuse a comparison (Task 2).
4. Repair changes a requirement to make itself pass: preserve original criteria and reject weakening (Task 3).
5. Failed/empty repeated outputs and unequal final evidence: keep failures in denominators and expose input differences (Task 4).

## File and contract map

New production modules live in `src/market_briefing/`: `prior.py` (bounded frozen reads), `research_state.py` (state/condition validation and continuity), `comparisons.py` (daily endpoint contracts and arithmetic), `evidence_gates.py` (question requirements and attempts), and `research_audit.py` (sidecar manifest and integrity verification). `evaluation/` contains task loading, execution, metrics and grading export in separate focused modules. Existing CLI/stages/review/bundle modules only orchestrate these responsibilities.

Add schemas under `resources/schemas/`: `research-state.v1.json`, `research-structured.v1.json`, `analysis-structured.v1.json`, `comparison-input.v1.json`, `research-questions.v1.json`, `research-audit.v1.json` and `evaluation-tasks.v1.json`. Register these exact kinds in `contracts.schema_path`. Internal structured envelopes contain existing payloads plus state/questions; existing public schemas stay byte-compatible. Do not duplicate the public nested schemas manually: resolve/generate stage schemas from packaged definitions, with packaging and provider-subset tests.

Stage files: `prior-inputs/` with exact input bytes, `prior-inventory.json`, `comparison-input.json`, `comparisons.json`, `research-state.json`, `continuity.json`, `research-questions.json`, numbered attempt files and `research-audit.json`. Record canonical content digests for JSON validation and raw byte hashes for imported files. Audit manifest uses fixed relative filenames, not caller-controlled arbitrary file traversal.

### Task 1: Freeze prior research and track structured judgments

**Files:** Create `prior.py`, `research_state.py`, `research_audit.py`, state/audit schemas; modify `contracts.py`, `cli.py`, `editor.py`, `validate.py`, `review.py`, `publication.py`; create `tests/test_prior.py`, `tests/test_research_state.py`, `tests/test_research_audit.py`.

**Interfaces:**
- `load_prior(run_dir: Path | None, market_date: str, cutoff: datetime) -> dict` returns `{status, identity, audit_status, documents, inventory}`; absent input has null identity and empty documents/inventory.
- `freeze_prior(prior: dict, destination: Path) -> dict` writes imported exact bytes and returns their fixed-name inventory. Reader limits: 2 MiB/file and 16 MiB aggregate; reject duplicate JSON keys/non-finite constants, symlinks or paths escaping the supplied run root.
- `validate_state(state: dict, analysis: dict, evidence: dict, prior: dict) -> None` checks `market.research-state.v1`, current claim/evidence references and prior condition IDs.
- `build_continuity(prior: dict, state: dict) -> dict` returns deterministic per-horizon change labels plus model-supplied, validated current explanations.
- `write_audit(run_dir: Path, members: dict[str, dict]) -> dict` / `verify_audit(run_dir: Path, briefing: dict, evidence: dict, analysis: dict) -> None` bind fixed sidecars to the existing quality warnings via `Research audit SHA256: <digest>`.

State has `short_term` (`1-4w`) and `long_term` (`6-12m`). Each holds `assessment_status=available|insufficient`, `direction=constructive|neutral|cautious|null`, `confidence=high|medium|low|null`, path, supporting `claim_ids`, counterevidence and conditions. Available states require direction/confidence and supporting current claims; insufficient states require null direction/confidence and a concrete gap. Available long-term state must match `analysis.thesis`; never programmatically map insufficient to neutral. Preserve the public legacy thesis without treating it as a structured assessment; reject contradictory available projections.

Condition IDs are a code-derived digest of origin identity and frozen text. Prior condition assessments are `observed|not_observed|unresolved|retired`; observations reference current evidence, and `not_observed` additionally needs explicit window/coverage. Unknown IDs, missing prior-condition assessments or reuse of an ID with changed text fail. Legacy prior material preserves text but has no inferred short-term direction. Changes are separate booleans/labels for direction and confidence, plus `became_assessable`, `became_insufficient`, `unchanged` or `unavailable`.

- [x] **1.1 Write failing import/integrity tests.** `test_prior_cutoff_includes_generation_and_review_time` asserts rejection when prior generation/review is after cutoff despite an earlier market date. `test_legacy_prior_has_no_inferred_short_term` asserts unavailable. `test_invalid_supplied_prior_never_starts_model` asserts no stage invocation; no-prior input returns absent.
- [x] **1.2 Run red tests.** `python -m pytest tests/test_prior.py tests/test_research_state.py tests/test_research_audit.py -q`; expect missing interfaces or failed assertions.
- [x] **1.3 Implement prior/state validation and freezing.** Verify existing briefing findings and numeric bindings, source-review hashes when supplied, date/cutoff order and hashes of read bytes. Never reopen untrusted original paths after freezing to supply a model. Add changed-read, duplicate-key, size and symlink fixtures.
- [x] **1.4 Write state/continuity tests.** `test_condition_absence_is_unresolved`, `test_unknown_condition_identity_rejected`, `test_available_long_term_matches_thesis`, `test_insufficient_is_not_neutral` and a two-date supported direction/confidence transition; assert current claims/evidence and original condition text are retained.
- [x] **1.5 Implement deterministic continuity and audit checks.** The marker binds all required members; verify recomputes state/continuity and refuses missing/changed sidecars. Missing marker plus present new audit is invalid. Legacy runs with neither preserve existing validation. Bundle copies supporting files and revalidates their staged copies.
- [x] **1.6 Run green tests and legacy regressions.** Include `tests/test_numeric_bindings.py`, `tests/test_publication.py`, `tests/weekly/test_context.py`; test marked bundles fail when one member is removed or tampered with and resumed editing rejects changed frozen prior bytes.
- [x] **1.7 Commit the increment.** `git add` only owned files; commit `feat: add frozen prior research and daily continuity`.

### Task 2: Calculate comparable historical observations

**Files:** Create `comparisons.py`, comparison schema and `tests/test_daily_comparisons.py`; modify `cli.py`, `contracts.py`, `research_audit.py`, `numeric_bindings.py` and their focused tests. Leave weekly contracts/rounding unchanged unless an explicit tested pure-helper extraction is needed.

**Interfaces:**
- `load_comparison_input(path: Path | None, cutoff: datetime) -> dict` performs bounded, duplicate-safe immutable input validation.
- `calculate_comparisons(payload: dict, cutoff: datetime) -> dict` returns `{schema_version, endpoints, results, diagnostics}` with formula, original inputs, output unit, observation/reference periods and stale flags.
- `merge_comparisons(evidence: dict, comparisons: dict) -> dict` adds original endpoints/sources and computed observations with deterministic collision-safe IDs; it never mutates input objects.

Input `market.comparison-input.v1` holds sources, endpoints and `{start_id,end_id,method}` requests. Endpoint identity includes `series_id,instrument,metric,provider,unit,adjustment,contract` (contract explicitly null for non-futures), source ID, value, observed/known timestamps, reference period, verification, actual/estimate classification and complete/lagged status. Identity must agree for a numeric comparison; timestamp availability must be no later than cutoff. Lagged endpoints remain marked and cannot satisfy a question requiring complete coverage.

Use Decimal with a declared four-decimal output precision: `return=(end/start-1)*100` for positive price levels in `usd|index_level|ratio`; `yield_change=(end-start)*100` basis points from percent yields; `absolute_change=end-start` in the original unit except percent levels produce percentage points. Zero/nonpositive prices are invalid for returns. Retain raw endpoint values and never convert a percentage-return series into a level series. Missing endpoints yield diagnostics, not fabricated results; malformed identities or incompatible present endpoints fail.

- [x] **2.1 Write failing arithmetic tests.** Assert 100→110 gives 10 percent; percent yield 4.0→4.25 gives 25 basis points; percent level 1→3 gives 2 percentage points. Parametrize reversed times, non-finite/estimate inputs and mismatched identity/provider/contract/adjustment with rejection assertions.
- [x] **2.2 Run red tests.** `python -m pytest tests/test_daily_comparisons.py -q`; expect unavailable functions or failed behavior.
- [x] **2.3 Implement endpoint loading/arithmetic/provenance.** Preserve both endpoint source references and deterministic IDs; claims using derived observations must also retain endpoint references. Bind calculation inputs/results in research audit and recompute before numeric rendering or bundling.
- [x] **2.4 Add missing/stale/integrity tests.** `test_missing_endpoint_is_not_zero`, `test_lagged_endpoint_stays_visible`, `test_changed_basis_blocks_delta`, `test_derived_observation_requires_both_endpoint_refs` and `test_changed_formula_breaks_audit` assert the named behavior. Ensure same literal evidence IDs from different inputs are namespaced deterministically.
- [x] **2.5 Run green and weekly comparison regressions.** `python -m pytest tests/test_daily_comparisons.py tests/test_numeric_bindings.py tests/weekly/test_contracts_comparisons.py -q`.
- [x] **2.6 Commit.** `feat: calculate comparable daily research evidence`.

### Task 3: Integrate structured research, evidence gates and bounded repair

**Files:** Create `evidence_gates.py`, structured stage/question schemas and `tests/test_evidence_gates.py`, `tests/test_structured_research.py`; modify `research.py`, `analysis.py`, `cli.py`, `editor.py`, `research_audit.py`, packaged researcher/challenger/analyst/editor prompts and relevant stage fixtures.

**Interfaces:**
- `validate_questions(questions: dict, evidence: dict, comparisons: dict) -> dict` returns deterministic acceptance findings for each question and dependent horizon.
- `validate_attempt(original_requirements: dict, candidate: dict, evidence: dict, comparisons: dict) -> dict` rejects changed criteria, reports findings and preserves attempt identity.
- `research_structured(session: dict, cutoff: datetime, config: dict) -> tuple[dict,dict,dict]` returns evidence, existing analysis projection and structured audit members; `analyze_structured(evidence: dict, config: dict) -> tuple[dict,dict]` returns analysis and members for frozen inputs.
- Internal research envelope is `{sources,observations,analysis,state,questions}`; frozen analysis envelope is `{analysis,state,questions}`. Reuse v1 definitions by controlled schema construction. Initial live requirements are frozen before challenge/repair.

Questions contain 2–3 unique IDs with relevance, dependent `short_term|long_term` horizons, requested evidence kind, frozen requirements (classification, periods/series, complete coverage if needed), current evidence/comparison IDs, status and gaps. A comparison-requiring question cannot pass on one endpoint. Actual/estimate metadata is checked rather than inferred from prose. A blocked question marks only its dependent structured assessment insufficient; if a valid available state survives, do not lower confidence automatically. Semantic relevance remains a model assertion for source review.

Default structured live flow: initial research → optional deep challenge with reconciled IDs → deterministic gates → at most one corrective model invocation → revalidation → frozen audit → editor. There is no correction when findings are empty. Existing per-stage timeouts apply; failure/timeout of correction remains an auditable failed attempt and cannot publish a passing state. Freeze each raw candidate/findings before retry. No repair may change the original requirements or discard failed history. Evidence insufficiency may yield a valid explicitly insufficient state; integrity failures remain errors.

- [x] **3.1 Write failing gate/repair tests.** `test_two_endpoints_required`, `test_classification_mismatch_rejected`, `test_missing_evidence_only_blocks_dependent_horizon`, `test_repair_cannot_weaken_original_requirements`, `test_repair_attempt_limit_is_one` and `test_failed_repair_preserves_previous_findings` assert exact statuses/call counts.
- [x] **3.2 Run red tests.** `python -m pytest tests/test_evidence_gates.py tests/test_structured_research.py -q`.
- [x] **3.3 Implement schemas, deterministic gates and stage orchestration.** Retain original live search requirements for research/challenge; frozen analysis/editing disable search. Reconcile changed evidence IDs into state/question references as well as analysis claims. Use JSON runtime records, not mutable shared flags.
- [x] **3.4 Wire CLI defaults and resumption.** Add `--previous-run PATH` and `--comparison-input FILE` to daily research/analyze/run. Load/freeze before model execution; record audit mode and input hashes in request/run. New generation always uses structured stages even without prior inputs. Archived validate/bundle paths remain version-aware; old `edit` revisions with changed prompt/schema resources still require a new revision.
- [x] **3.5 Update editor context and marker verification.** Editor receives frozen state/continuity and linked current facts, preserves insufficient status without inventing direction, and still uses numeric tokens. It cannot turn prior prose into a new numeric observation. Audit projection validates agreement with available long-term public thesis. Include an absence/gap explanation when state cannot be expressed faithfully.
- [x] **3.6 Run integration tests with fake model executables only.** Full two-date pipeline, absent/legacy prior, standard/deep paths, new-state ID reconciliation, malformed output, future data, timeout, changed dependency on resume and missing-sidecar bundle refusal. Confirm final evidence/analysis/briefing validate against unchanged public contracts and source approval remains false.
- [x] **3.7 Run focused existing daily/weekly regressions and commit.** `feat: enforce evidence gates in structured daily research`.

### Task 4: Evaluate frozen research with honest denominators

**Files:** Create `evaluation/__init__.py`, `evaluation/tasks.py`, `evaluation/runner.py`, `evaluation/metrics.py`, `evaluation/grading.py`, task schema, `tests/test_evaluation_tasks.py`, `tests/test_evaluation_runner.py`, `tests/test_evaluation_metrics.py`; modify CLI registration/docs/README and packaging tests.

**Interfaces:**
- `load_tasks(path: Path) -> dict` validates unique task IDs, input revisions, experiment kind, candidate paths and optional perturbations; all explicit inputs are bounded/frozen with hashes.
- `evaluate(tasks: dict, out_dir: Path, *, live: bool=False, model_config: dict | None=None) -> dict` creates a new external output directory, executes selected experiment kinds and returns its manifest/summary identity.
- `summarize(attempts: list[dict]) -> dict` returns counts/denominators, failures, quantities/fingerprint consistency, input equality, optional structured direction/confidence agreement and manual metrics as null when unlabeled.
- `export_grading(attempts: list[dict], out_dir: Path, seed: int) -> dict` writes shuffled paired grades and a separate source key; no automatic human scores.

CLI: `market-briefing evaluate --tasks FILE --out-dir DIR [--live]` and `market-briefing evaluation-grades --run-dir DIR --out-dir NEW_DIR --seed INTEGER`. Offline is default; no model executable starts without `--live`. Live model/effort settings are explicit and inherited into all invocation records. Standard/deep pairs may have different final evidence: compare requested task/starting inputs separately from final evidence digests. No production edit setting disables binding; legacy comparison mode is scoped within the evaluator and emits evaluation records only.

Experiment kinds: `counterfactual`, `repeat`, `paired`, `failure`. Counterfactual uses cloned fixed candidates and selected observation fields only; it reports numeric provenance, never semantic direction correctness. Repeat consumes recorded candidates or explicit live edits; failed/empty outputs stay in all-attempt totals and cannot count as invariant. Paired supports standard/deep research and bound/legacy editing, saving each final input digest. Failure fixtures retain exception/error classification and expected-versus-observed behavior.

Manifest records source commit plus working-tree digest, packaged prompt/schema digests, input/task hashes, model/effort, actual stage/search mode, experiment parameters and timestamps. Raw attempts and frozen task copies remain inspectable. Summaries contain n/N, missing/unassessable fields and actual durations. No predictive-accuracy/significance/optimal-budget claim is computed from synthetic fixtures. A common numeric fingerprint does not establish source truth or language quality.

- [x] **4.1 Write failing task/runner tests.** Reject duplicate IDs, invalid kinds, path escapes and pre-existing output directories. `test_default_evaluate_never_invokes_model` asserts no executable/call; `test_counterfactual_changes_only_target_quantity` asserts cloned inputs and unaffected quantities.
- [x] **4.2 Run red tests.** `python -m pytest tests/test_evaluation_tasks.py tests/test_evaluation_runner.py tests/test_evaluation_metrics.py -q`.
- [x] **4.3 Implement loader, isolated runner and summaries.** Reuse producer validation/rendering APIs. The evaluation artifact kind is never accepted by bundle/review. Save failure records before aggregating; elapsed timers measure execution, not invented queue latency.
- [x] **4.4 Add denominator/pairing/grade tests.** `test_failed_repeats_are_not_invariant`, `test_missing_structured_state_is_unassessable`, `test_live_challenge_final_evidence_difference_visible`, `test_no_human_labels_yields_null_metrics`, `test_grade_source_key_is_separate`, `test_production_binding_is_unchanged_after_legacy_experiment` and raw-output tampering rejection.
- [x] **4.5 Add CLI fake-process tests and docs.** Exercise offline counterfactual/repeat/paired/failure cases, an explicitly invoked fake live stage, immutable output and grade export. Document limitations and commands in `docs/research-continuity.md` and `docs/evaluation.md`; link both from README and local-run docs.
- [x] **4.6 Run green tests and commit.** `feat: evaluate frozen daily research and export paired grades`.

## Final verification and integration

- [x] Run full offline pytest with a unique basetemp under `DATA_ROOT/quant-market-briefing/checks/`; run Ruff lint/format and locked-environment wheel/source builds. Import the built wheel and read all new schemas/prompts from packaged resources.
- [x] Complete an independent whole-branch review; reproduce and fix important findings with tests before proceeding. Review semantic limits separately from fixable reference/integrity bugs.
- [x] Fetch/query current main, validate any combined changes and create a PR against the user's repository. Wait for six CI matrix jobs on the current result; never bypass required controls.
- [x] Merge under standing authorization, preserve public noreply commit identity, verify merged branch/CI and leave production untouched. Remove only this task's remote/local branch and worktree after confirming no unique unsaved work.
- [x] Report PR/commit, actual validation, remaining real-model/human-evaluation limits and cleanup outcome.

## Plan self-review

All four spec deliverables map to Tasks 1–4; audit/storage/review obligations span each task and final integration. All five Review Focus cases have named tests in their owning tasks. Names/signatures and artifact filenames are shared consistently; new model contracts remain internal and existing public/weekly contracts are preserved. Explicit real-model research-quality evaluation and production activation are excluded. Execution method and this written plan require user review before implementation.

Implementation and independent review completed. Integration checks and merged-result verification are recorded in the PR. Negative condition findings remain unresolved until verified interval completeness can be represented; point observations cannot establish absence.
