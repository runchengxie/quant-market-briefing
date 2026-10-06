# quant-market-briefing

[![CI](https://github.com/runchengxie/quant-market-briefing/actions/workflows/ci.yml/badge.svg)](https://github.com/runchengxie/quant-market-briefing/actions/workflows/ci.yml)

A small, independently runnable U.S. post-close research producer. It can research the live web or read frozen evidence, then run a separate Chinese editor. The result is five plain Chinese paragraphs, machine-readable claims and source provenance.

Current release: local generation and reviewed file bundles. The intel context exporter, briefing-specific consumer adapter and production scheduler are follow-up integration work.

## Install and run

Requires Python 3.11–3.13, uv and a separately authenticated Codex CLI.

```sh
uv sync --locked --group dev
uv run market-briefing --help
uv run market-briefing research --date latest --data-root /external/briefings
uv run market-briefing research --date YYYY-MM-DD --context /external/intel-research.json --data-root /external/briefings
uv run market-briefing run --date YYYY-MM-DD --evidence /external/evidence.json --data-root /external/briefings
```

Models and effort are explicit. Research defaults to gpt-6-astra/xhigh, challenge to gpt-6-astra/high and editing to gpt-6.1-sol/medium. Override with --analyst-model/--analyst-effort, --reviewer-model/--reviewer-effort and --editor-model/--editor-effort. User config is ignored and authentication is inherited. Unsupported account/model settings fail rather than silently selecting an alternative. Verify access as the actual service user before deployment.

These are provisional settings for a quality-focused deep preview, not an experimentally established optimum. Research has the broadest task, challenge concentrates on an existing draft's gaps, and editing works only from frozen inputs. The same model in two separate invocations can still share blind spots. Higher effort and more searches do not establish forecast accuracy. Compare configurations using the same frozen inputs and multiple sessions before choosing a daily operating budget.

The default --research-depth deep runs research, a separate live-search challenge and editing. --research-depth standard omits the challenge for a two-call comparison. Frozen-input run/analyze retain their offline research behavior. Each model stage has a default 1,200-second timeout, so the full deep workflow can take longer; --timeout-seconds overrides this per-stage limit.

Run outputs default to ~/data/quant-market-briefing. Each explicit rerun creates a new immutable revision. No command sends notifications or installs schedules.

## Commands

| Command | Input | Output |
| --- | --- | --- |
| research | Session date, optional intel context and live web search | Frozen evidence, analysis and five-paragraph draft |
| analyze | Evidence file and session date | New revision with evidence and analysis |
| edit | --run-dir containing analysis | Five-paragraph draft |
| validate | --run-dir containing draft | Mechanical findings and exit status |
| bundle | --run-dir, --review, --producer-commit | Reviewed publication files |
| run | Evidence file and session date | Both model stages and mechanical findings |

See [Local run](docs/local-run.md), [Contracts and integration](docs/integration.md), and [Chinese editorial rules](src/market_briefing/resources/prompts/editor.zh-CN.md).

`research --context` accepts the existing intel web-research `schema_version: "1.0"` document as unreviewed search leads. The importer checks session, timestamps, source URLs and size before starting a model, then freezes a snapshot and input hashes in the revision. Research and challenge must verify source originals before using those leads as evidence. Candidate acceptance or an upstream review label does not grant publication approval. See [context import and follow-up scope](docs/context-import.md).

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

GitHub Actions runs the offline suite, Ruff lint/format checks and wheel/source builds on Ubuntu and Windows with Python 3.11, 3.12 and 3.13. It triggers for pull requests, pushes to main and manual dispatch. Runtime, development and build tooling dependencies are installed from the lockfile before installing the project; installation and packaging use that environment without build isolation. Temporary test and build outputs stay outside the source tree. CI does not install Codex, use model credentials, generate live reports or deliver notifications. Its checks establish software behavior, not research quality or source approval.

## Research templates

The [original Chinese framework](src/market_briefing/resources/prompts/research-framework.zh-CN.md) is preserved as supplied. The [researcher template](src/market_briefing/resources/prompts/researcher.zh-CN.md) adds search, provenance and JSON rules. Both are packaged resources, alongside the editor template. Runtime options belong in the CLI/configuration; explanatory documents belong in docs.

Research now requires separate short-term and six-to-twelve-month direction judgments, the most likely path, main drivers, counterarguments and invalidation conditions. Direction is independent of confidence. Evidence-backed inferences need not repeat a source's conclusion, but must retain linked observations and uncertainty. Missing data affects only dependent judgments; an unsupported direction remains explicitly unassessable. The editor preserves these judgments without choosing a direction or raising confidence. No bullish outcome, probability or price target is prescribed.

Research and challenge explicitly use `web_search="live"` and each require a completed search event. Frozen analysis and editing explicitly disable search. The challenge searches material gaps, comparable historical changes and counterevidence, then returns a complete reconciled evidence/analysis document. research.initial.json preserves the initial result, challenge.candidate.json the revision, and final evidence.json/analysis.json the editor inputs. Search completion does not establish that every source supports every claim; publication still requires the separate hash-bound source review.

Each invocation records requested model/effort, CLI version, prompt/schema hashes, search mode and start time, with a separate completion record for successful stages. These records describe explicit CLI settings; the JSONL protocol does not expose the backend-served model, so they do not claim independent attestation of that model. request.json and run.json retain stage settings, and resumed editing inherits its original model/effort.

`--date today` is the scheduler default and skips nontrading days. `--date latest` selects the most recent completed session for manual use. The evidence cutoff is the research start time, not the historical close. A historical run therefore represents research as of that cutoff, not a reconstructed close-time vintage. Source publication timestamps may be null when the page gives only a date. Missing or inaccessible financial data stays in missing_inputs.

Deep review retains the raw candidate. Changed source or observation records receive fresh identifiers deterministically, with references updated and the mapping saved to `challenge.reconciliation.json`. This changes identifiers only and does not certify corrected facts.
