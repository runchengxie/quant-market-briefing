# quant-market-briefing

A small, independently runnable U.S. post-close research producer. It can research the live web or read frozen evidence, then run a separate Chinese editor. The result is five plain Chinese paragraphs, machine-readable claims and source provenance.

Current release: local generation and reviewed file bundles. The intel context exporter, briefing-specific consumer adapter and production scheduler are follow-up integration work.

## Install and run

Requires Python 3.11–3.13, uv and a separately authenticated Codex CLI.

```sh
uv sync --locked --group dev
uv run market-briefing --help
uv run market-briefing research --date latest --data-root /external/briefings
uv run market-briefing run --date YYYY-MM-DD --evidence /external/evidence.json --data-root /external/briefings
```

Stage models can be set independently with --analyst-model and --editor-model. If omitted, the Codex executable's built-in default applies; user config is ignored and authentication is inherited. Verify authentication and model access as the actual scheduled service user before deployment.

Run outputs default to ~/data/quant-market-briefing. Each explicit rerun creates a new immutable revision. No command sends notifications or installs schedules.

## Commands

| Command | Input | Output |
| --- | --- | --- |
| research | Session date and live web search | Frozen evidence, analysis and five-paragraph draft |
| analyze | Evidence file and session date | New revision with evidence and analysis |
| edit | --run-dir containing analysis | Five-paragraph draft |
| validate | --run-dir containing draft | Mechanical findings and exit status |
| bundle | --run-dir, --review, --producer-commit | Reviewed publication files |
| run | Evidence file and session date | Both model stages and mechanical findings |

See [Local run](docs/local-run.md), [Contracts and integration](docs/integration.md), and [Chinese editorial rules](src/market_briefing/resources/prompts/editor.zh-CN.md).

## Trust boundaries

Structure, evidence links, numeric tokens and text formatting are mechanically checked. These checks cannot certify semantics, correct financial units or causal explanations. Source approval is a separate review record bound to the exact evidence, analysis and briefing hashes. The producer cannot manufacture that approval.

The publication envelope uses research.platform-publication.v1 and the legacy consumer ID market-intel for quant-intel-platform. A generic manifest verifier does not implement the new market.briefing.v1 renderer.

Evidence may include verified numeric observations and verified textual company/macro events. Estimates retain their original reference periods. Unverified/null observations are missing inputs. Analyst/editor prompts treat supplied content as data and prohibit new facts or external research.

## Development

```sh
uv run pytest --basetemp /external/checks/unique-run
uv run ruff check .
uv run ruff format --check .
uv build --out-dir /external/build
```

Tests use synthetic evidence and fake model executables, with no paid model, market-data or messaging calls.

## Research templates

The [original Chinese framework](src/market_briefing/resources/prompts/research-framework.zh-CN.md) is preserved as supplied. The [researcher template](src/market_briefing/resources/prompts/researcher.zh-CN.md) adds search, provenance and JSON rules. Both are packaged resources, alongside the editor template. Runtime options belong in the CLI/configuration; explanatory documents belong in docs.

Research now requires separate short-term and six-to-twelve-month direction judgments, the most likely path, main drivers, counterarguments and invalidation conditions. Direction is independent of confidence. Evidence-backed inferences need not repeat a source's conclusion, but must retain linked observations and uncertainty. Missing data affects only dependent judgments; an unsupported direction remains explicitly unassessable. The editor preserves these judgments without choosing a direction or raising confidence. No bullish outcome, probability or price target is prescribed.

The research command explicitly uses `web_search="live"` and requires a completed search event. Frozen analysis and editing explicitly disable search. Research and editing are two model calls. Search completion does not establish that every source supports every claim; publication still requires the separate hash-bound source review.

`--date today` is the scheduler default and skips nontrading days. `--date latest` selects the most recent completed session for manual use. The evidence cutoff is the research start time, not the historical close. A historical run therefore represents research as of that cutoff, not a reconstructed close-time vintage. Source publication timestamps may be null when the page gives only a date. Missing or inaccessible financial data stays in missing_inputs.
