# Integration boundaries

## Producer

quant-market-briefing owns the analyst prompt, Chinese editor prompt, generated analysis/draft contracts, validation and local publication bundles. Source schemas and prompt templates are wheel package resources under src/market_briefing/resources.

Versioned inputs and outputs:
- market.evidence.v1: frozen numeric/text observations and source identities.
- market.analysis.v1: supported claims, thesis, six analytical sections and missing inputs.
- market.briefing.v1: trusted run identity, five paragraphs, thesis, sources and mechanical checks.
- market.source-review.v1: separate source decisions bound to all three document hashes.
- research.platform-publication.v1: existing file identity, disclosure and consumer envelope.

## Consumer

quant-intel-platform owns rendering, report/card composition and delivery receipts. Its current consumer identifier is market-intel. Do not substitute the repository name in publication-manifest consumers.

The producer emits the existing manifest fields: schema_version, generated_at, producer_repository, producer_commit, run_id and artifacts. Each artifact has artifact_id, relative_path, schema_version, sha256, media_type, audience and consumers. All artifact paths are fixed relative filenames, never caller-provided traversal paths.

The existing generic manifest verifier checks paths/hashes/disclosure. A follow-up consumer adapter must recognize market.briefing.v1 plus market.source-review.v1, verify the review binding, apply existing source/disclosure rules, then render brief_text. The envelope alone never authorizes a draft to be displayed publicly.

No import from daily_messenger or another owner repository is used. Existing intel approved-index evidence rules and deployment disclosure gates remain authoritative.

## Context export

`research --context` now accepts existing intel web-research v1.0 JSON as frozen,
unreviewed search leads. It does not convert candidates into approved evidence.
See [context import](context-import.md) for checks, provenance and follow-up scope.

A follow-up intel exporter may assemble existing authoritative market/report artifacts into market.evidence.v1. It must preserve observation dates, estimate periods, source identities, missing data and audit state. It must not claim ownership of market series merely because it exports a report context.

## Deployment

quant-intel-deploy owns runtime version pins, external configuration, service-user authentication, scheduling, destinations, recovery and delivery receipts. A follow-up schedule should run after the exchange close plus a configurable availability delay, with a bounded retry window for late inputs.

Deduplicate delivery using product + market_date + revision. Producer retries are not second delivery authorization. Deploy from an immutable release path, never a development worktree.

## Limitations

Mechanical numeric checks compare exact digit tokens against linked evidence values/reference periods. They do not prove correct units, signs, time interpretation, Chinese-number wording or causal reasoning. Rounding/scaling is intentionally unsupported in this release. All such meaning needs independent review.

The exchange calendar is library-based, not a live exchange-closure feed. Emergency closures require operator/calendar updates. Stage caching and automatically repaired prose are intentionally absent from v1; failures retain diagnostics and explicit reruns create fresh revisions.
# Live research input

`market-briefing research --date latest` can produce evidence directly through Codex live web search. A quant-intel-platform evidence exporter is optional for this mode. The producer still needs the intel consumer adapter for rendering/delivery, and deployment owns schedules.

The model returns `research.v1.json` with sources, observations and analysis. Python supplies the selected session, close, cutoff and collection metadata, validates both nested contracts and freezes the result before editing. Research sources are model-checked observations, not independently approved publication evidence.

The evidence unit enum additionally accepts percent for levels/percentage returns and basis_points for basis-point changes. Legacy percentage_points remains valid for differences between percentages. A text observation can retain exact financial units and periods without conversion.
