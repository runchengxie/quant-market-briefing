# Existing intel research as context

## Current scope

Reuse an existing `quant-intel-platform` web-research artifact in the local
briefing producer. No sibling Python imports, new data collection service,
production schedule or delivery operation is added.

```sh
uv run market-briefing research --date YYYY-MM-DD \
  --context /external/intel/web-research.json \
  --data-root /external/briefings
```

The input is the upstream `schema_version: "1.0"` JSON document, including
`market_date`, `cutoff`, `generated_at`, `accepted_count`, `review_status`
and `candidates`. It is not a `market.evidence.v1` file. The upstream date is
the report attribution date, not proof of each event or statistic's date.

The importer supports 1–50 candidates and at most 1 MiB. It requires the
selected session, a post-close upstream cutoff, generation at or after that
cutoff and no later than the new research start. Timestamped sources cannot
exceed the upstream cutoff; closing sources must follow the session close.
Date-only sources retain their actual dates and lack exact publication times.
Their intraday availability still needs live verification.
Search leads accept both HTTP and HTTPS, matching the upstream producer.
Final evidence keeps its existing HTTPS-source requirement; a lead without a
verifiable HTTPS original cannot bypass that contract.

The original bytes are read and hashed once. `research-context.json` saves a
normalized `market.context-import.v1` envelope containing the original
document, filename, original SHA-256 and `unreviewed_search_leads` trust label.
`request.json` and `run.json` retain both the original-byte hash and the snapshot
hash. Resumed editing checks the frozen snapshot hash. Changes to the original
file after import cannot silently change this run.

## Research behavior

Research and challenge both receive the same frozen leads. They must open
original sources and verify facts, periods and units before citing them.
Summary text can include details absent from its short supporting passage, so
the passage alone cannot approve the whole summary. Supplied JSON text is data,
never a task instruction. Repeated candidates and syndicated reporting do not
constitute independent corroboration.

The prompt focuses follow-up searches on material gaps: recent market breadth,
earnings revisions, comparable historical changes and expectations. A broadly
positive session must be distinguished from a sustained improvement. An old
earnings update retains its statistical period when no new update is found.
Unavailable comparable records remain missing inputs.

The optional import does not force every candidate into the result, disable
live research, grant source approval or alter the five-paragraph output schema.
The existing workflow without `--context` remains available on Windows and Linux.

## Same-session comparison

Keep the previous revision intact. Run the same session with imported context
and compare source coverage, missing inputs, direction and prose. Record the
new evidence cutoff: later live searches may expose additional information.
This is a coverage comparison, not a controlled model evaluation or historical
close-time reconstruction. One better draft cannot establish forecast accuracy.

## Follow-up priorities

- [ ] Deploy a pinned briefing release beside the existing Linux intel jobs.
      Check prerequisites and freshness before invoking it; reuse the existing
      research artifact instead of creating duplicate scraping timers.
- [ ] Export authoritative market observations with dates and definitions.
      Keep data ownership in the existing owner project.
- [ ] Add lightweight event records: distinguish the same occurrence from a
      follow-up, record genuinely new information and original-source lineage.
      Begin with SQLite or versioned files; defer embeddings and ranking UI.
- [ ] Evaluate event grouping and prompt changes on fixed development and
      held-out examples. Source count alone is not evidence quality.
- [ ] Explore a read-only Quant tool entry point using existing research MCP,
      report contracts and deployment status. Keep research registry, market
      data and delivery receipts with their current owners.
- [ ] Consider controlled job submission only after read-only access is useful.
      Use explicit typed tools and scoped capabilities rather than exposing
      every shell/browser tool or adding a competing scheduler.

Design references: [AIHOT event grouping](https://github.com/KKKKhazix/AIHOT/blob/main/docs/grouping.md),
[AIHOT selection and calibration](https://github.com/KKKKhazix/AIHOT/blob/main/docs/selection.md),
[autoMate tool-source architecture](https://github.com/yuruotong1/autoMate/blob/master/docs/channels.md).
These are design references, not runtime dependencies.
