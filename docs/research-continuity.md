# Daily research continuity

Daily `research`, `analyze` and `run` now produce structured short-term (one to four weeks) and long-term (six to twelve months) assessments, two or three material evidence questions, acceptance findings and a research audit. Public five-paragraph output and schemas are unchanged. Legacy validation and weekly generation retain their original contracts.

```sh
market-briefing research --date latest --previous-run /external/briefings/PREVIOUS_DATE/r0001 --comparison-input /external/comparable-endpoints.json --data-root /external/briefings
market-briefing validate --run-dir /external/briefings/CURRENT_DATE/r0001
```

Both additional inputs are optional and explicit. The producer does not search an archive or infer a previous run. Prior market dates and cutoffs must precede the current ones; prior generation, collection and review timestamps cannot exceed the current cutoff. Historical replay uses the actual recorded information vintage, not a reconstructed close-time database. A supplied invalid prior fails before model execution. No prior yields an explicit absent status. Unknown publication timestamps do not prove historical source availability.

Direct previous input files are frozen byte-for-byte under `prior-inputs/`, with hashes and a parsed summary in `prior-inventory.json`. Source review is verified when present; otherwise the prior remains unreviewed research context. Prior interpretations are not current evidence and must be rechecked against original sources. The importer verifies the original research audit when present; it retains its direct audit proof without recursively copying every ancestor's archive directory.

`research-state.json` separates direction, confidence and assessment status. Insufficient assessments have null direction/confidence and a concrete gap. Legacy prior runs have no inferred short-term direction; only explicitly structured views are compared at that horizon. `continuity.json` reports direction/confidence changes and transitions into or out of assessability. These are descriptive changes, not evidence of forecast skill.

The public v1 long-term thesis requires a direction and cannot encode null/unassessable. If long-term evidence remains insufficient, generation retains a draft with a projection error and source review cannot approve it. It is not silently mapped to neutral or published with the original directional compatibility field. An insufficient short-term state can be expressed as an explicit gap in the prose when the long-term projection remains valid.

Conditions receive deterministic identities from their origin and original text. Every prior condition is explicitly observed, unresolved or retired. Observed outcomes need linked current verified actual evidence. Negative findings remain unresolved because evidence v1 cannot validate interval completeness; `not_observed` is rejected even with a declared window. Retirement, wording changes and elapsed horizons are not scored as falsification or success.

## Comparable endpoints

`market.comparison-input.v1` contains `sources`, `endpoints` and `requests`. The packaged schema is the authoritative complete format. Each endpoint declares ID, series ID, instrument, metric, provider, adjustment, contract (null for non-futures), value/unit, observation and known-at timestamps, reference period, source ID, actual/estimate classification, verification and complete/lagged status.

Requests supply start/end IDs and `return`, `yield_change` or `absolute_change`. Returns require positive comparable price levels; percent-valued yield changes produce basis points; absolute changes in percent levels produce percentage points. Results are rounded deterministically to four decimals, with original endpoints/formulas retained. Existing source quantities are never implicitly rescaled. Different identities/providers/contracts/adjustments, reversed times, unavailable or non-finite observations are rejected. Missing endpoints generate diagnostics, not zero; lagged values remain visible.

Historical inputs must be supplied through an explicit owner artifact. This is not a new market-data collector or a similarity/backtest engine. The application namespaces imported IDs, retains both endpoint source references and recomputes derived observations before rendering and bundling.

## Evidence gates and repair

The initial stage chooses two or three material questions and freezes their criteria and dependent horizons. Code checks references, classifications, coverage, requested series/periods and computed comparisons. Relevance and causal meaning remain research assertions for independent review. A question needing a comparison cannot pass on one endpoint or a missing calculated result.

Only dependent structured judgments become insufficient when gates remain unmet. Deep research performs the independent live-search challenge; if deterministic gates still fail, at most one additional corrective invocation is allowed. Frozen analysis uses the same bound with search disabled. Failed attempts remain in numbered records, and repair cannot change the original question, criteria or dependent horizons. Correction timeouts preserve the gap; integrity failures stop generation. The editor receives the accepted state and must preserve its direction/uncertainty without treating compatibility thesis fields as evidence that an insufficient view is neutral.

`research-audit.json` binds the state, continuity, direct prior inventory, comparable inputs/results, questions and attempt history. Its digest is carried in existing briefing quality metadata and is therefore covered by the exact independent source-review hash. `validate`/`bundle` recompute the records and reject missing or changed sidecars. Resumed editing also checks the recorded input/resource digests. Bundles retain supporting files; existing public consumers do not automatically understand the new research state.

This workflow does not certify source truth, metric wording, causality or predictive accuracy. Source approval remains separate, and generation never activates delivery or production schedules.

Negative condition findings remain `unresolved`: evidence v1 has point observations but no verified interval-completeness contract. A declared window or an earlier observation cannot establish absence across an interval; `not_observed` is rejected until such coverage can be validated. Legacy revisions with an unbound structured state sidecar are rejected.
