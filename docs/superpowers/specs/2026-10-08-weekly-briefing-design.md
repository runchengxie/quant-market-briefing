# U.S. weekly market briefing

Status: proposed written design; the user approved the content direction, but has not reviewed this specification or an implementation plan.

## Outcome and scope

Produce a Chinese weekend research report explaining what changed during the week, why it matters to U.S. markets, and what to watch next week. Include global macroeconomics, monetary policy, material corporate earnings, war and other geopolitical developments. Success means a reader can identify the main weekly drivers, compare them with the previous view, inspect supporting sources, and distinguish observed facts from inference and scheduled future events.

The first release is a local producer in quant-market-briefing. It generates immutable drafts and supports separate source review. Consumer rendering and deployment scheduling are follow-up work owned by quant-intel-platform and quant-intel-deploy. No production schedule or message delivery is introduced by this specification.

## Approach

Three options were considered: concatenate daily reports, add a weekly product to the existing producer, or create another repository. Concatenation loses changes in expectations and repeats evolving stories. A separate repository duplicates model invocation, provenance and storage infrastructure. Extend the existing producer with explicit weekly commands and contracts while preserving daily interfaces.

Reuse Codex stage execution, invocation records, external storage safeguards, immutable revisions and publication-envelope conventions. Weekly calendar selection, research validation, report editing and review binding have separate product contracts; do not force a week into the daily market_date or five-paragraph schema.

## Report structure

1. Core weekly judgment: a concise conclusion, main drivers, change from the previous weekly view, confidence, counterevidence and invalidation conditions. The principal horizon is the coming one to four weeks; longer-term implications are explicitly separated where supported.
2. Macro and policy: material releases and revisions, central-bank decisions and communications, and changes in rate expectations. Record reference periods, release dates, units and data lags. Expectations and surprises require timestamped sources; absent consensus data remains missing.
3. Weekly events: prioritize approximately five to ten material events when evidence permits, without filling a quota. Cover earnings, geopolitical developments and policy changes according to relevance. Each event explains what happened, what is new, the observed response and the inferred transmission to markets.
4. Market response: comparable weekly equity, Treasury, dollar, gold and oil observations, with sector or breadth context when available. Explain whether these support the thesis, rather than assuming a news item caused a price change.
5. Next-week watchlist: verified scheduled releases, earnings and policy events with dates, timezone, source, potential relevance and outcomes that could change the thesis. Distinguish confirmed dates from tentative schedules and ongoing unscheduled risks.

Use readable Chinese headings, paragraphs and compact lists; no five-paragraph limit. Proposed editorial target: approximately 1,500–2,500 Chinese characters, with provenance separate from the main text. This is a soft target, not grounds to invent or omit material evidence.

## Week and information cutoff

Identify the product by the Monday start date of a New York civil week. The retrospective window is Monday 00:00 through the exclusive following Monday 00:00 in America/New_York. The default latest selector chooses the most recent week whose Friday 23:59:59 has elapsed; a Saturday run can therefore include Friday after-close earnings. Capture the actual research-start evidence_cutoff in UTC and display its New York equivalent. Retrospective event coverage ends at the earlier of the week boundary and cutoff. Sunday reruns can include newly available weekend events within that same week; later historical reruns explicitly record the later information vintage.

For market returns use the last completed XNYS session before the week and the last session within the week, with explicit endpoint dates. Friday holidays and early closes come from the exchange calendar. Do not call a Thursday endpoint a Friday close. A week with no sessions returns a documented skipped result. Cross-asset series use their own completed observations; differing endpoints, stale data and missing values remain visible. Percentage returns use comparable positive price levels; yield changes are basis points. Preserve instrument identity and adjustment basis, including futures contract/roll caveats. Never compare different instruments as one continuous series.

Next-week calendar entries may have event times beyond cutoff, but their supporting announcements must have been available by cutoff. This requires separating event time, source publication time, observation/reference period and collection time. Unknown publication timestamps stay null and require review; they cannot silently establish historical availability. An explicit --week-start must be a Monday and must pass the completed-week gate. Historical generation is research at its recorded cutoff, not a reconstruction of what was known that week.

## Inputs and research stages

Optional explicit --daily-context-dir and --previous-weekly-run inputs provide search leads and comparison context. Load supported producer artifacts only, freeze an input inventory with file hashes and audit status, namespace source identifiers per input run, and retain missing-day diagnostics. No sibling source imports, directory ownership guesses or automatic copying of shared datasets. Missing daily reports do not block live weekly research.

Daily model output remains unreviewed unless accompanied by a valid bound review. Even reviewed facts require period and cutoff checks. Previous views are attributed as previous interpretations, not market facts. With no prior weekly report, state that no week-to-week thesis comparison is available. Evolving stories are grouped by a stable topic/event key with separate dated developments; deduplication must retain corrections and escalation.

Stages: weekly live research; independent invocation for live-search challenge of material gaps, contradictions, period comparisons and counterevidence; Chinese editing from frozen reconciled evidence only; mechanical validation. Both live stages require completed search events. The challenge preserves originals and assigns fresh identities to changed evidence. Reuse current explicit model/effort defaults and overrides as provisional settings, recording each invocation. No new optimal-cost or predictive-accuracy claim is made.

Prefer official statistical releases and central-bank documents for macro facts, issuer filings and investor-relations releases for earnings and schedules, and attributed credible reporting for unfolding geopolitical events. Claims by parties to a conflict are attributed and uncertainty retained. Critical contested facts need corroboration or explicit unresolved status. Model retrieval and mechanical validation never grant source approval.

## Contracts, commands and storage

Add weekly-specific schemas: market.weekly-evidence.v1, market.weekly-analysis.v1, market.weekly-briefing.v1 and market.weekly-source-review.v1, plus stage-output schemas as needed. Python supplies product identity, week boundaries, cutoff, generated time and revision. Contracts reject unexpected properties and validate unique IDs, reference integrity, periods and timestamps.

Evidence holds sources, observations, events, scheduled events and missing inputs. Analysis holds fact/inference claims linked to evidence, thesis and comparison to a hashed previous report, selected events, market comparisons and watchlist. Briefing holds five named sections with claim IDs, readable text, sources and mechanical findings; source_audit_passed remains false. Scheduled events have separate known-at and event-time fields. Missing coverage is expressed per category, never silently treated as no events.

Proposed CLI:

```sh
market-briefing weekly-research --week-start latest --data-root EXTERNAL_ROOT
market-briefing weekly-research --week-start YYYY-MM-DD --daily-context-dir DAILY_ROOT --previous-weekly-run PREVIOUS_RUN --data-root EXTERNAL_ROOT
market-briefing weekly-edit --run-dir WEEKLY_RUN
market-briefing weekly-validate --run-dir WEEKLY_RUN
market-briefing weekly-bundle --run-dir WEEKLY_RUN --review REVIEW_FILE --producer-commit FULL_COMMIT
```

Runtime artifacts live at <resolved DATA_ROOT>/quant-market-briefing/weekly/<week-start>/rNNNN/. Resolve roots from the explicit workspace configuration or supplied --data-root. Daily paths remain unchanged. Lock by weekly product and week; explicit reruns allocate new revisions. Store request/run records, frozen inputs, initial/challenged research, reconciliation, evidence, analysis, briefing JSON/text and validation diagnostics outside Git. Failed stages retain diagnostics and cannot become validated drafts.

Review binds exact weekly evidence, analysis and briefing hashes, product/week/revision and every final referenced claim. Only approved claims can be bundled. Use research.platform-publication.v1 with distinct weekly artifact identity and schemas; retain consumer ID market-intel. No weekly renderer is assumed in the existing consumer. The first release verifies local bundles; downstream consumers must explicitly add weekly support before accepting them.

## Validation and acceptance

Offline tests cover week selection, DST, Friday holidays, early closes, no-session weeks, historical cutoff semantics, weekend revisions, upcoming scheduled events, stale cross-asset endpoints and unit calculations. Contract and fake-Codex tests cover input hashing, missing context, source ID collisions, evolving-event deduplication, initial/challenge preservation, evidence links, editor invention, failed search, timeouts, invalid drafts and exact review binding. Existing daily tests must remain passing.

Run focused offline tests, the full offline suite, Ruff checks and wheel build with outputs outside source. One explicitly invoked real weekly research run can assess prose, coverage, actual sources and diagnostics after implementation; it is a draft, not proof of forecast accuracy or source approval. Do not invent a live result in offline fixtures.

Acceptance: independently runnable weekly draft with the five sections; explicit week and cutoff; auditable events and future calendar; comparable market endpoints; previous-view comparison or an explicit absence; preserved missing inputs; reviewed local bundle support; daily interface compatibility.

## Follow-up and review boundary

After written-spec approval, prepare an implementation plan for producer-only work. Consumer presentation and deployment require their own repository instructions, contracts and validation. A future weekend schedule must specify cutoff, timezones, stable release paths, bounded retries and delivery identity product + week-start + revision; none is activated here.

Design self-review: checked the daily five-paragraph constraint, product separation, external roots, holiday endpoints, weekend event coverage, future-event timestamps, historical vintage, source-review authority and repository ownership. Proposed defaults (length and completed-week gate) are explicit and can be adjusted at written-spec review.
