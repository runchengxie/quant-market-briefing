# Daily research continuity and evaluation

Status: written design approved by the user on 2026-10-23. Implementation plan approved and Native execution selected by the user on 2026-10-23. Builds on merged quantity-binding commit `f251b7a` / PR #11.

## Intended outcome

Make successive U.S. daily briefings a traceable research record. A researcher should be able to identify which observations changed, which interpretation changed, why the change is supported, and whether an earlier invalidation condition was actually observed. Add frozen-input experiments that distinguish software correctness from model research quality and quantify the incremental value of challenge and binding stages.

The user requested the remaining improvements discussed after reviewing PostClose. This design covers four deliverables: cross-day judgments, deterministic historical comparisons, evidence acceptance and reproducible evaluation. It preserves natural Chinese five-paragraph daily output and independent source approval. It does not introduce trading signals, a frontend, delivery, schedules or production configuration.

## Current code and ownership

- `quant-market-briefing` owns live daily research, challenge, frozen analysis/editing, numeric bindings, immutable revisions and reviewed local bundles.
- Daily `analysis.v1` stores a structured long-term thesis; its short-term view, drivers and invalidation conditions are partly prose. Prompts already request them, so an additional prompt alone would not establish tracking.
- Weekly context imports already freeze prior producer artifacts and label historical interpretations separately from market facts. Weekly comparison code calculates returns and yield changes with instrument/basis checks.
- `quant-intel-platform` already exposes `quant-research-review` for verified public daily snapshots. It describes changes in facts and statements; it does not evaluate hypothesis success and does not consume the producer's new internal research record.
- The producer must not import sibling source. This release stays within the producer; owner data is supplied through explicit versioned files. A future public consumer adapter is separate work, not a dependency of the local research features.

## Approach and alternatives

Recommended: extend the existing producer with frozen prior inputs, a structured research sidecar, deterministic comparison inputs and a separate evaluation CLI. Reuse immutable writes, invocation metadata, evidence validation, numeric binding and source review. New schemas are internal producer artifacts; published `market.briefing.v1` remains unchanged.

Alternatives considered: only add historical prose to prompts, or implement a cross-repository research database and dashboard. Prompt-only memory cannot enforce provenance or track conditions reliably. A new database/dashboard expands deployment and consumer contracts before the local research behavior can be evaluated. Neither alternative is selected.

## A. Frozen prior research and cross-day continuity

Add explicit optional `--previous-run PATH` to daily `research`, `analyze` and `run`. No automatic directory search or implicit latest pointer. The prior input must be an earlier daily producer revision with valid evidence, analysis and briefing. Read any numeric-binding record and independent review through the same integrity checks as validation/bundling. Reject symlink escapes, oversized or ambiguous JSON, changed findings and dates/cutoffs that do not progress forward. A later historical backfill is not proof that the prior report was available at the earlier market close.

Freeze exact prior input bytes and their inventory into the new revision before model execution. Store report date, run/revision, cutoff, generation time, hashes and audit status. Optional valid source review labels the prior material reviewed; it does not exempt sources from current-period verification. Without review, it remains explicitly unreviewed. A missing prior input yields `prior_status=absent`, not a fictional previous position. A supplied malformed prior input fails before model execution rather than silently disappearing.

Use a new internal `market.research-state.v1` sidecar. Record separate short-term and long-term assessments, each with horizon, assessment status, direction, confidence, path, supporting current claim IDs, counterevidence and invalidation conditions. `assessment_status=insufficient` has null direction/confidence; it must never be scored as neutral. Long-term available assessments must agree with existing `analysis.thesis`. The existing public thesis is retained for compatibility and is not used as proof that an insufficient assessment was neutral. If the existing output cannot express a required conclusion faithfully, fail the new structured path rather than silently inventing a projection.

Condition identity is derived by code from origin run/hash and frozen condition text. Reuse an identity only through an explicit prior reference; changed wording does not automatically mean the same condition. Each prior condition gets `observed`, `not_observed`, `unresolved` or `retired`, with current evidence IDs and explanation. `not_observed` requires evidence and a defined observation window; missing coverage is `unresolved`. Reaching a forecast horizon, removing a condition or changing a direction does not establish success/failure or falsification. Retired conditions remain in the history.

Compare available structured views by horizon. Program-determined changes include unchanged direction/confidence, direction change, confidence change, became assessable and became insufficient. The model explains drivers using current claims; code does not infer causality. Legacy prior runs without structured state retain their original prose, long-term thesis and condition text, but no short-term direction is extracted by regular expression or guessed from sentiment. Those tracking fields remain unavailable.

Pass frozen prior interpretations to research and challenge as data to reassess, not instructions or current evidence. Freeze current research state before editing. The editor may mention a material change only when the state links it to supported current claims. The full tracking record stays outside the five-paragraph prose.

## B. Deterministic comparable historical evidence

Add an explicit optional `--comparison-input FILE` with a versioned endpoint contract. Each numeric endpoint includes stable series identity, instrument, metric, provider, unit, adjustment, futures contract where applicable, observation time, reference period, publication/availability information, verification/classification and source URLs. Run-local evidence IDs alone do not establish series identity.

Support a small declared method set: price return from positive comparable levels, yield change in basis points from percent-valued yield levels, and absolute change with explicit output units (percent levels change in percentage points). Reject non-finite values, missing identity, mixed instruments/contracts/adjustments/providers, reversed or equal endpoint times, estimates presented as realized endpoints and availability beyond the recorded cutoff. Missing or stale endpoints yield explicit diagnostics; do not fill zero, interpolate or choose a replacement series.

Requests identify endpoints and method; Python computes results and records the formula, inputs, units, periods and stale flags. Do not subtract daily percentage returns as if they were cumulative returns. Do not infer market breadth or an earnings revision trend from a single observation. Scope is supplied comparable observations, not a new market-data collector or full historical similarity/backtesting engine.

Include original endpoints in frozen evidence. Derived observations must have deterministic IDs and an accompanying provenance record naming both endpoint observations/sources and the formula. Claims using a result also retain endpoint references. Quantity binding renders the derived value only after the calculation/provenance is recomputed successfully. No synthetic third-party source or independently approved status is manufactured for a derived result.

Prefer extracting shared pure arithmetic within this repository over importing weekly product schemas into the daily path. Preserve existing weekly contracts and rounding behavior; add explicit adapters and compatibility tests if arithmetic is shared.

## C. Evidence acceptance for material questions

Persist two or three material research questions chosen for their potential to change the market judgment, not a universal checklist that must always be filled. Each question declares its relevance, requested evidence kind, required periods/identity when a comparison is needed, retrieved current evidence IDs, status and unresolved gap. Relevant examples include participation breadth, earnings revision concentration and financing conditions.

Deterministic gates verify referential integrity, actual/estimate classification, cutoff, declared endpoint comparability, required coverage and calculated outputs. They do not certify source truth or that a particular observation semantically answers a question. The model's relevance assessment remains inspectable and subject to source review.

Unmet evidence requirements restrict only dependent judgments. Mark them insufficient and retain the gap; do not make every market view neutral or low-confidence. Repairs may obtain different supporting evidence or narrow a claim, but cannot lower the acceptance criteria or overwrite an earlier failed attempt. Use existing stage timeouts and a bounded correction budget with persisted attempts; no unbounded search or autonomous rule optimization.

To avoid forcing new optional fields into the public contract, use internal stage schemas containing the existing research payload plus structured state/questions. Python projects the original evidence/analysis artifacts only after validating the additional records. Existing archived artifacts remain loadable; new structured mode cannot silently drop state on a retry or resumed edit.

## D. Frozen-input evaluation

Add a separate local `evaluate` command with explicitly supplied tasks/input revisions, experiment kind and a new external output directory. Default offline mode uses recorded candidates and synthetic fixtures; real model execution requires explicit invocation. Nothing in CI calls paid models, market-data providers or messaging services. Evaluation never changes production flags, canonical evidence or shared latest pointers.

Initial experiment types:

1. Counterfactual rendering: clone evidence, change a selected quantity/unit/period, rerender a fixed bound candidate and test that affected quantities follow the input while unrelated quantities stay unchanged. This tests provenance behavior only; it does not demonstrate that direction or causal prose adjusts correctly.
2. Repeated fixed-evidence editing: compare bound observation/value/unit/period fingerprints and prose changes across recorded or explicitly requested model outputs. Failed attempts remain failures, not successful invariance. Record direction/confidence agreement only when structured state exists; repeated editing alone cannot measure research-direction stability.
3. Paired stage comparisons: compare standard versus deep research on the same supplied task/starting context, and binding versus an explicitly isolated legacy editor path on the same frozen evidence/analysis. Live challenge may retrieve different evidence, so record final evidence differences and do not label that comparison identical final inputs. Evaluation-only bypasses cannot disable production validation or produce publishable bundles.
4. Failure fixtures: conflicting units/periods, stale endpoints, absent prior reports, evidence gaps, invalid references and model timeout/invalid output. Report what failed and why.

Each run saves task/input copies and hashes, code/tree identity, prompt/schema digests, requested model/effort, experiment parameters, raw attempts, validation findings, measured duration, sample counts and machine/human-readable summaries. Output creation is immutable and rejects a pre-existing experiment directory.

Separate automatic provenance/contract metrics from human judgments of source correctness, relevance, explanation and readability. A valid citation is not a correct citation. No human labels means N/A, not perfect accuracy. Report denominators, excluded/unassessable cases and failures. Do not infer predictive accuracy, optimal budget or statistical significance from small synthetic fixtures. Provide a blinded paired grading export with its source key separate; do not fabricate ratings or a formal gold dataset.

## Integrity, storage and publication

Daily revisions remain under the explicit external data root. New files include frozen prior inputs/inventory, comparison inputs/results, research questions/attempts, research state and continuity output. Evaluation uses a caller-selected separate output directory. No source-repository runtime data, sibling imports or credential relocation.

Record new input/resource hashes in request/run metadata and reject changed dependencies on resumed editing. Bind integrity-critical sidecars into a deterministic research-audit digest carried by the final briefing's existing quality metadata, following the quantity-binding pattern. Validation and bundling require and recompute the marked sidecars. Review's exact briefing hash therefore binds the audit digest. Legacy artifacts without a marker use their original checks; a new marked run with a missing sidecar fails closed. Preserve source_audit_passed=false and require the existing independent review before bundling.

Consumer-visible schema and consumer ID `market-intel` remain unchanged. Copy supporting provenance files into local bundles without claiming that existing public adapters understand the new research state. No changes in `quant-intel-platform` or `quant-intel-deploy` are required for this local release.

## Delivery order and acceptance

Implement four reviewable increments in one isolated producer task: (1) frozen prior input and structured state/continuity, (2) comparable endpoints and derived provenance, (3) evidence gates and bounded attempts, (4) evaluation runner, paired export and documentation. Each increment gets focused offline tests before broader regression. If an increment reveals a need to change an external consumer contract, stop and revise that scope explicitly.

Acceptance includes: a two-date synthetic scenario showing supported view changes and unresolved conditions; legacy/no-prior behavior; future-cutoff and tampered-input rejection; comparable and incompatible endpoint cases; missing evidence narrowing only dependent judgments; failed repair not weakening gates; repeat/counterfactual/failure summaries with honest denominators; immutable outputs and separate approval; and unchanged legacy daily/weekly tests.

Validation: full offline pytest, Ruff lint/format and wheel/source builds; independent code review; PR CI on Linux/Windows and Python 3.11–3.13; revalidation against current main before integration; merged-branch verification and task-only cleanup under existing authorization. Optional real-model research-quality experiments remain a separate explicit run and cannot confer source approval or activate production.

## Review checkpoint

This document is the concrete scope and interface proposal, not evidence of implementation. After written-design approval, create a task-level implementation plan and select execution per the development skill workflow. Standing merge/cleanup authorization remains in effect and does not need to be requested again.

Design self-review checked owner boundaries, existing weekly reuse, public schema compatibility, absent legacy short-term state, cutoff/vintage semantics, conditional evidence coverage, derived units, source-review authority and evaluation claims. No production configuration or model-cost experiment is included.
