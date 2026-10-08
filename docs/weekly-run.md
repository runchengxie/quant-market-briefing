# Local weekly market research

The weekly producer researches a completed New York civil week and writes an immutable Chinese draft. Its five sections cover the core judgment, macro/policy, material events including earnings and geopolitics, market response, and the next-week calendar. It does not install schedules or send messages.

## Generate

```sh
uv run market-briefing weekly-research --week-start latest --data-root /external/quant-market-briefing
uv run market-briefing weekly-research --week-start YYYY-MM-DD --workspace-config /private/shared/workspace.toml --daily-context-dir /external/daily-runs --previous-weekly-run /external/previous-week/r0001
```

`--data-root` denotes the project root. Alternatively an explicitly supplied `--workspace-config` TOML file must contain an absolute `data_root`; the producer appends `quant-market-briefing`. Explicit data-root wins. There is no guessed machine-local configuration path. Weekly outputs live at `<project-root>/weekly/<Monday>/rNNNN/`; daily outputs retain their existing paths.

`latest` selects the most recent week whose Friday 23:59:59 New York gate has elapsed. Explicit dates must be Mondays and pass the same gate. The event window runs from Monday local midnight through the earlier of the following Monday or actual research-start cutoff. Saturday/Sunday reruns can add weekend developments in new revisions. Historical reruns retain their actual information cutoff and are not historical-vintage reconstructions. A week with no XNYS sessions skips without calling a model.

Price comparisons use the last session before the week and the last session inside the week. Friday holidays and early closes use the exchange calendar. Cross-asset endpoints retain actual dates, units, instrument identity, contract and adjustment basis; stale observations must be disclosed. The producer calculates supplied comparable endpoints, rounded to four decimal places, rather than trusting model-calculated weekly percentages. Missing endpoints stay missing.

## Research and provenance

Defaults match the daily quality preview: Astra/xhigh for research, Astra/high for the challenge, and Sol/medium for editing; each stage has a 1,200-second timeout. Use `--analyst-model/--analyst-effort`, corresponding reviewer/editor options, `--research-depth standard`, or `--timeout-seconds` for explicit overrides. These defaults are provisional, not proven optimal. Both live stages require completed search events; editing has search disabled.

Daily context is optional and supports this producer's daily revision directories. The highest complete revision per session supplies unreviewed leads, with exact input hashes and missing-day diagnostics. A valid independent review is required to record reviewed status. At most 32 daily revisions are examined; individual JSON is limited to 2 MiB and aggregate context to 16 MiB. Symlinks escaping supplied roots are rejected. A previous validated weekly draft can supply an attributed prior interpretation; without it, the report explicitly has no previous-week comparison.

Frozen context, original and challenged research, reconciliation, grouped event developments, evidence/analysis, invocation logs and metadata remain in the revision. `briefing.json`, `briefing.txt` and `validation.json` distinguish failed drafts from mechanically valid drafts; neither establishes source approval. The standalone text includes the trusted week, UTC/New York cutoff, draft label and missing-input disclosure. The approximately 1,500–2,500 Chinese-character target is a warning only.

## Resume, validate and review

```sh
uv run market-briefing weekly-edit --run-dir /external/weekly/YYYY-MM-DD/r0001
uv run market-briefing weekly-validate --run-dir /external/weekly/YYYY-MM-DD/r0001
uv run market-briefing weekly-bundle --run-dir /external/weekly/YYYY-MM-DD/r0001 --review /external/review.json --producer-commit FULL_40_CHARACTER_GIT_SHA
```

Resume editing only if no final briefing/text/validation output exists. Input hashes, resources, identity and saved editor settings must match; changing any requires a fresh research revision. Failed candidates are retained. Never overwrite final output or an approved revision.

Independent source review must inspect originals and bind exact evidence/analysis/briefing SHA-256 hashes, week, run and revision, then approve exactly all final referenced claims. The review schema is `market.weekly-source-review.v1`. The local bundle uses `research.platform-publication.v1`, weekly schemas, internal audience by default and consumer ID `market-intel`. Existing daily consumer adapters do not imply weekly support. Consumer rendering and production scheduling require follow-up integration in their owner repositories.
