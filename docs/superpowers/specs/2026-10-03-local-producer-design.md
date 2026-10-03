# Quant Market Briefing — design for review

Status: local producer implemented and independently reviewed; consumer integration and production activation remain follow-up work.

## Intent

Produce a daily U.S. post-close briefing using the user's fundamental-first, macro-aware investment template, followed by a separate Chinese editing stage. Deliver five natural Chinese paragraphs and machine-readable provenance to quant-intel-platform. Keep the producer independently runnable and small.

## Repository evidence

Read-only inspection on 2026-10-03 found existing U.S. report generation and reviewed-research workflows in runchengxie/quant-intel-platform. Relevant documents:

- docs/how-to/run-daily-report.en.md
- docs/how-to/us-daily-data-boundaries.en.md
- docs/how-to/reviewed-us-daily.md
- docs/platform-publication.en.md

The current consumer requires `market-intel` in manifest consumers, validates safe relative paths and SHA-256, and separates public/internal disclosure. Research completion does not constitute source approval. Existing approved-index evidence currently accepts AP original pages or AP carried by ABC News. Production scheduling belongs to quant-intel-deploy. Do not assume that a new briefing payload is already supported by the generic manifest verifier.

The installed `codex exec --help` confirms noninteractive stdin input, `--output-schema`, `--output-last-message`, `--json`, `--ephemeral`, and configurable models. Authentication availability under a scheduled service account still needs a runtime check. No particular access-token product or account entitlement is assumed.

## Architecture decision

Create quant-market-briefing as a standalone Python producer. Reuse frozen, versioned facts and reviewed source artifacts through files or public CLI exports. Do not import daily_messenger internals. Do not add strategy or backtesting dependencies. Market data production remains with its authoritative data owner; intel can export an assembled report context without becoming the owner of underlying market series.

Alternatives: implement all writing inside intel (less initial integration, tighter coupling); reuse quant-research/platform (unnecessary strategy/runtime dependencies). The standalone producer best fits the requested iteration speed and file-based handoff.

## Minimal first release

Start with explicit report dates and imported evidence. Add automated context export, consumer integration, and scheduling only after local generation is reviewable. Initial commands: `analyze`, `edit`, `validate`, `bundle`, and `run`. `bundle` writes files locally; it does not deliver messages.

Source code, prompts, schemas and synthetic fixtures live in the repository. Reports, evidence, logs and execution state live under a configurable external data root, defaulting to ~/data/quant-market-briefing. Credentials and machine settings live outside the repository in the existing owner configuration namespace.

## Data contracts

`market.evidence.v1`: market, market_date, session timezone, scheduled close, evidence cutoff, collection time, source records and observations. Each observation has an ID, value, unit, reference period, actual/estimate classification, source ID, observation time, source publication time when known, and verification state. Percent changes and yields use explicit percentage-point units. Missing values remain missing.

Distinguish same-day market facts from weekly earnings estimates, monthly macro releases and quarterly financials. Retain original observation dates. Market-wide FCF and insider statistics are optional, methodology-dependent inputs. Never force all template sections to contain a numerical claim.

`market.analysis.v1`: thesis, horizon, confidence, fundamentals, supporting reasons, contrary evidence, sector/macro interpretation and catalysts. Every factual claim references evidence IDs. Interpretations identify their supporting facts and are not mislabeled as verified facts. Preserve uncertainty, missing inputs and invalidation conditions.

`market.briefing.v1`: identity, report date, cutoff, generation time, run ID, revision, five paragraph objects, claim/evidence references, deterministic brief_text, thesis, sources and validation findings. Python supplies identity and metadata from trusted inputs rather than letting the model choose them. Derive brief_text by joining paragraphs with two newline characters.

`research.platform-publication.v1`: follow the existing manifest contract exactly. Use `market-intel` as the consumer identity. Include producer repository/commit, run ID, artifact identity, relative path, schema version, media type, SHA-256 and audience. Consumer support for `market.briefing.v1` needs its own adapter and repository change.

## Research and editing

The analyst reads frozen evidence and applies the original fundamental/macro template, preserving three supporting arguments, two meaningful risks and a conclusion when evidence supports them. Current-day reactions and 6–12 month views must remain distinct. Quarterly EPS growth is not an assumption for forward twelve-month EPS growth. Earnings yield minus Treasury yield is not a complete equity risk premium model. Falling AI spending is not automatically bearish; its effect depends on demand, monetization and capital efficiency.

The editor reads analysis plus referenced evidence. It cannot browse for new facts, introduce numbers, change a forecast into an actual, or strengthen tentative causality. It writes exactly five paragraphs: daily market reaction; earnings and cash flows; valuation and rates; sector differentiation and AI returns; forward observations and risks. Daily emphasis can vary to avoid repetitive boilerplate.

Chinese style: plain native prose, Chinese punctuation, no Markdown, lists, emoji, headings, emphasis, quotation marks, semicolons or dashes in prose. Avoid English jargon, literal translations, promotional phrasing, jokes, canned summaries and unnecessary negative-positive contrast sentences. Accurate company names and necessary identifiers are allowed. Target 800–1,200 Chinese characters as a soft editorial range, not a reason to fabricate detail.

## Validation and release state

Schema validation proves structure only. Separate structure_passed, evidence_links_passed, editorial_rules_passed and source_audit_passed. Do not publish invented validation percentages or a blanket facts_validated flag after a model finishes.

Check dates, cutoff, units, evidence references, five paragraphs, new numerical claims, estimate/actual preservation, prohibited formatting and manifest hashes deterministically where possible. Semantic causality and faithfulness require an independent claim review; rule checks alone cannot certify them.

Outputs begin as draft. A structurally valid and edited result becomes validated_draft. Source audit binds its decisions to evidence, analysis and final briefing hashes. Only fully approved claims permit a reviewed bundle. Any later edit invalidates its review. Failed, deferred or incomplete required checks cannot promote the product to publishable. Public disclosure is enforced by the consumer and deployment gate.

## Runtime reliability

Invoke Codex through a subprocess argument array, with UTF-8 stdin, explicit working directory, schema path, output path, timeout and exit-code handling. Keep stage logs and final JSON separate. Configurable stage models inherit an explicit deployment configuration; no hardcoded model upgrade.

Use bounded retries for transient failures, not schema or evidence failures. Lock each report date to prevent overlapping runs. Cache stages only when input hashes, prompt hashes, schema versions and model configuration match. Use atomic writes and immutable revision directories. Do not overwrite an approved report or update latest pointers on failure.

Use the official exchange session calendar and America/New_York for session selection, including holidays, daylight saving time and early closes. A scheduled run selects that day's completed session; a holiday produces skipped status rather than republishing Friday. Explicit manual replay may target an earlier session but cannot claim evidence collected later was available at that historical close.

Schedule after close plus a configurable source-availability delay. Handle delayed provider observations with a bounded retry window and missing-data status. Read the deployment owner's scheduler conventions before choosing Windows Task Scheduler, systemd or another runtime.

## Delivery and rollout

Phase 1: local producer with frozen evidence input, prompts, contracts and a reviewable bundle. Phase 2: intel context exporter and consumer adapter, following each repository's branch/worktree/PR rules. Phase 3: deployment-owned shadow schedule, retaining outputs without sending messages. Phase 4: explicitly authorized production activation and destination configuration, preserving existing source review gates.

Use market_date + product + revision for artifact identity, with consumer delivery receipts to prevent duplicate pushes. Producer retries never imply a second delivery.

## Acceptance criteria for subsequent implementation

A frozen synthetic session can run through both stages and produce five paragraphs with traceable claims. Missing evidence cannot be fabricated. Invalid dates, units, claim references, schema output, changed hashes and concurrent runs fail safely. Replays retain their cutoff semantics. Holiday and early-close selection is correct. Intel renders only supported, reviewed bundles and retains a delivery receipt.

Design preparation used read-only inspection. Subsequent approved implementation passed 68 offline tests plus package and publication-contract checks. No real model generation, public report publishing, scheduling or notifications were run.

## Review decision

The user authorized implementation in the current session. The local producer is implemented; source-data export, the consumer adapter and scheduling are separate follow-up integrations. Production authorization remains a later deployment-owner gate.
