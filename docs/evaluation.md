# Frozen-input evaluation

Evaluation is a local, immutable research diagnostic. It never grants source approval or activates delivery. The default is offline: it reads recorded candidates, freezes their bytes and does not start a model. Real calls require explicit `--live`, use the specified model/effort and consume the normal account budget. CI uses synthetic inputs and fake executables only.

```sh
market-briefing evaluate --tasks /external/tasks.json --out-dir /external/evaluation/new-run
market-briefing evaluation-grades --run-dir /external/evaluation/new-run --out-dir /external/evaluation/new-grades --seed 42
```

The task schema is packaged as `market.evaluation-tasks.v1`. A minimal recorded repeat example:

```json
{"schema_version":"market.evaluation-tasks.v1","tasks":[{"id":"example","kind":"repeat","run_dir":"/external/briefings/DATE/r0001","candidates":[{"label":"first","path":"/external/candidate-a.json"},{"label":"second","path":"/external/candidate-b.json"}]}]}
```

The baseline revision must pass its original validation, including bindings/audit sidecars when marked. Relative paths must stay under the task-file directory; explicit absolute input paths are accepted. Symlinks, duplicate JSON keys, oversized inputs and existing output directories are rejected. Output must be outside source repositories and outside input revisions. Input bytes are frozen before execution, so later source changes cannot silently change an experiment.

Kinds:

- `repeat` compares recorded bound editor candidates, or explicitly requested live editing of the same frozen evidence/analysis. `repeats` repeats the declared candidate sequence. Fingerprints include observation identity, metric, value, unit and reference period. Failed, empty or no-quantity outputs are never successful numeric invariance. Direction/confidence are not inferred from editing prose.
- `counterfactual` clones a fixed candidate and baseline evidence. Supply `changes` objects with `observation_id`, `field` (`value`, `unit`, `reference_period`) and `value`. Targets must actually be referenced. Unrelated bound quantities must stay unchanged. This tests numeric provenance, not whether directional or causal prose responds correctly.
- `paired` with `comparison=bound-legacy` requires exactly two recorded candidates with explicit modes `bound` and `legacy`, or explicit live execution of both. The legacy path is evaluator-local and cannot disable production binding. With `comparison=standard-deep`, recorded candidates are labeled `standard` and `deep` and contain `evidence`, `analysis`, optional `state`, and `starting_input_sha256` matching the canonical digest of the frozen baseline documents. A missing/mismatched receipt fails the attempt. Live mode runs standard/deep research and editing from the same declared starting prior/comparison inputs. Live searches may yield different final evidence and actual start cutoffs, which are retained and reported separately. These pairs must not be described as identical final inputs.
- `failure` processes recorded invalid candidates. Optional `expected_error` names the anticipated exception class. A record containing `synthetic_failure: "timeout"` represents an explicitly synthetic timeout, not a recorded real provider incident. Failed attempts stay in success denominators and are also counted separately against expected failure behavior.

Outputs contain frozen task/input copies, manifest, raw per-attempt records, aggregate `attempts.json`, `metrics.json` and `metrics.md`. The manifest records code revision/working-tree digest, resources, input hashes, requested settings and offline/live mode; live stages retain invocation logs with their actual explicit options. These are requested settings, not independent attestation of the backend-served model. Measured durations contain no invented queue latency.

Success and numeric consistency retain n/N. Paired final-evidence equality and assessable structured view agreement are separate fields. Missing structured state remains unassessable. Automatic checks do not become human source-correctness or readability scores: absent labels are null/N/A. No predictive accuracy, significance or optimal budget is asserted from these software experiments.

Grading export shuffles candidate placement and row order. Share only `grades.csv` with evaluators and retain `source-key.json` separately. Ratings are left empty. Wording may reveal provenance, so this does not establish perfect blinding. Incomplete pairs are excluded with coverage counts. Export does not automatically ingest ratings or certify sources.

All experiment directories are marked evaluation-only; the publication builder rejects them. No canonical evidence, source revision, shared current pointer, production flag or schedule is modified.
