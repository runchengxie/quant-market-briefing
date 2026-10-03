# Integration exploration

## Live research extension

The producer now includes an optional two-call web research/editor workflow and preserves the original Chinese research framework. Frozen-input workflows remain available. Live research retains sources, observations, structured analysis and search event logs outside the repository. The original need for an intel context exporter now applies only to the alternative frozen-input integration.

## Current evidence

The first live Codex experiment completed both stages using synthetic evidence. It produced five Chinese paragraphs, but the local evidence checks kept the result in draft status. Number tokens in instrument names/reference periods and unrelated estimate claims exposed alignment issues between editor claim references and the validator. This experiment demonstrates execution, not publication quality or real market accuracy.

Codex rejected missing explicit types in enum/constant schemas and the uniqueItems keyword. Schemas now have explicit types. A temporary generation schema omits uniqueItems, while final outputs still pass the original full local schema. Offline checks: 69 tests, Ruff and distribution builds passed.

## Integration boundaries

quant-intel-platform already supplies published daily market facts, macro observations and reviewed news. Consume a frozen versioned export, preserving source times, observation periods, units and review status. Retrieval time must not become publication time, and automated data quality must not become source approval.

Daily market data alone does not cover the full research prompt. Earnings revisions, comparable valuations, margins, free cash flow, insider activity and AI investment returns need separate weekly/quarterly snapshots. Missing inputs must remain explicit.

The existing publication manifest verifier can validate hashes and audience restrictions. A market.briefing.v1 consumer adapter is still required for rendering and delivery. quant-intel-deploy owns production schedules. No schedules or deliveries were enabled by this exploration.

## Next implementation

Define the frozen evidence export, including percentage levels versus percentage-point changes, instrument labels and coarse observation dates. Improve editor claim coverage and contextual numeric validation without granting arbitrary numbers. Repeat live generation against approved real evidence before connecting delivery.

Runtime artifacts and logs remain outside this public repository. Synthetic fixtures are not market reports.
