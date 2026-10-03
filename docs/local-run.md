# Local generation and source review

The first release takes a frozen market.evidence.v1 JSON file. It does not fetch market data. A synthetic schema example is available in tests/fixtures/synthetic-session.json; its values are fictitious and must never be published as real market facts.

## Evidence requirements

Use an actual XNYS session date and exchange close timestamp. All times are timezone-aware ISO timestamps. evidence_cutoff must be at or after close, and collected_at at or after cutoff. Source publication and observation times cannot exceed cutoff. Unknown publication times remain null.

Observations contain id, metric, value, unit, reference_period, classification, source_id, observed_at and verification. Units include percentage_points, count, usd, ratio, index_level and text. Percent return 0.73 means 0.73 percent, not a decimal return of 0.0073. No implicit conversions are performed. A string observation requires unit text. Source IDs and observation IDs are unique.

Numeric and textual inputs must be supported by the source review process that owns them. A field marked verified is a statement by the upstream producer, not independent proof obtained by this program. Source review must open originals and inspect periods, values, definitions, publication times and permitted disclosure.

## Generate

```sh
uv run market-briefing analyze --date YYYY-MM-DD --evidence /external/evidence.json --data-root /external/briefings
uv run market-briefing edit --run-dir /external/briefings/YYYY-MM-DD/r0001
uv run market-briefing validate --run-dir /external/briefings/YYYY-MM-DD/r0001
```

Or use run for both stages. The model has 600 seconds per stage by default. Override --timeout-seconds if needed. Logs are separate from final JSON. Only exit code 75 is retried, at most twice; schema/evidence/timeout failures are not automatically retried. A failed run retains diagnostics and cannot be mistaken for a reviewed product.

Model processes use read-only sandboxing, ephemeral sessions, explicit schema output and --ignore-user-config. Authentication still comes from the Codex runtime environment. These prompt restrictions are not an operating-system guarantee against all external model tools; deployment must separately control available credentials/tools.

Five paragraphs are joined with two newline characters into brief_text. Soft length/style warnings are preserved. Invalid drafts remain draft and return exit code 2. A mechanically valid draft is validated_draft, with source_audit_passed false.

Never edit an approved revision in place. Re-run generation for a new revision and obtain a new review. No stage cache is used in v1: this avoids silently reusing an output after inputs, prompts or models change.

## Review and bundle

Create an external review.json conforming to resources/schemas/review.v1.json after independent source inspection. Record reviewer, reviewed_at, market_date and the lowercase SHA-256 of the exact evidence.json, analysis.json and briefing.json bytes. Decide exactly every claim referenced by the final five paragraphs. Each decision records claim_id, status and reason. Only approved claims may be bundled. Deferred/rejected material must be removed in a newly edited revision and reviewed again.

```sh
uv run market-briefing bundle --run-dir /external/briefings/YYYY-MM-DD/r0001 --review /external/review.json --producer-commit FULL_40_CHARACTER_GIT_SHA
```

Default audience is internal. Explicit public packaging does not grant data disclosure rights or activate any downstream public publishing.

The bundle contains frozen evidence, analysis, unchanged final draft, review and publication manifest. The manifest lists the briefing and source review as separate consumer artifacts. The consumer must require both and verify their binding; the draft itself is not mutated to claim its own source audit passed.

## Session selection and replay

--date today selects the current New York calendar date. A nontrading day returns skipped and never silently republishes Friday. A pre-close invocation fails. Early closes and daylight saving changes come from exchange-calendars/XNYS.

An explicit historical session can be replayed, retaining the actual evidence_cutoff and collection time. This is not a historical data-vintage reconstruction. Data collected after that historical close must not be described as available at the original close.
