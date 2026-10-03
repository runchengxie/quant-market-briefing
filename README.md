# quant-market-briefing

A small, independently runnable U.S. post-close research producer. It reads frozen evidence, runs a fundamental/macro analyst, then a separate Chinese editor. The result is five plain Chinese paragraphs, machine-readable claims and source provenance.

Current release: local generation and reviewed file bundles. The intel context exporter, briefing-specific consumer adapter and production scheduler are follow-up integration work.

## Install and run

Requires Python 3.11–3.13, uv and a separately authenticated Codex CLI.

```sh
uv sync --locked --group dev
uv run market-briefing --help
uv run market-briefing run --date YYYY-MM-DD --evidence /external/evidence.json --data-root /external/briefings
```

Stage models can be set independently with --analyst-model and --editor-model. If omitted, the Codex executable's built-in default applies; user config is ignored and authentication is inherited. Verify authentication and model access as the actual scheduled service user before deployment.

Run outputs default to ~/data/quant-market-briefing. Each explicit rerun creates a new immutable revision. No command sends notifications or installs schedules.

## Commands

| Command | Input | Output |
| --- | --- | --- |
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
