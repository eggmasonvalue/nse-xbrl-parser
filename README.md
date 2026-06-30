# nse-xbrl-parser

[![Built with uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://docs.astral.sh/uv/)

`nse-xbrl-parser` is an offline-taxonomy NSE XBRL parser library for Python.

It is built for the common NSE failure mode where filings reference historical or incomplete taxonomy dependencies. The package ships a bundled taxonomy archive and resolves schemas locally, so Arelle validation and fact extraction do not depend on live taxonomy hosting.

## Install

```bash
uv add git+https://github.com/eggmasonvalue/nse-xbrl-parser.git
```

## Public API

- `parse_xbrl_facts(path)`
  - Returns a context-preserving fact table (`list[dict]`) with one row per concept/value/context/unit/decimals/period/basis/dimensions.
  - Use this for programmatic analytics and any workflow that must preserve every XBRL context.
- `build_xbrl_view(path, *, include_trace=False, include_validations=True, validate=True, use_cache=True)`
  - Returns a taxonomy-backed, JSON-serializable human view with `title`, `unit`, `columns`, `sections`, and `checks`.
  - Uses presentation and calculation linkbases when available, and falls back to safe period/basis/dimension grouping when presentation linkbases are absent.
  - Loads the Arelle model once and memoizes the result in-process (keyed by file identity and options). Pass `validate=False` to skip Arelle's full validation pass (measured ~5x faster on announcement filings; off by default until correctness parity is proven on linkbase-bearing statements). Pass `use_cache=False` to force a fresh load.
- `render_xbrl_markdown(view)`
  - Pure renderer from a `build_xbrl_view` dictionary to a readable markdown document.
  - Use this for human review, document stores, and doc-RAG/NotebookLM ingestion.
- `load_xbrl_model(path)`
  - Low-level context manager for advanced callers that need one shared Arelle model load.
- `clear_view_cache()`
  - Clears the in-process `build_xbrl_view` cache (for long-lived processes, tests, or refreshed taxonomy data).

The library intentionally does not expose a flat `{label: value}` parser. Any label-to-column flattening is an application-level projection built locally from the structured view or the fact table.

## Usage

```python
from pathlib import Path
from nse_xbrl_parser import build_xbrl_view, parse_xbrl_facts, render_xbrl_markdown

xml_path = Path("filing.xml")

facts = parse_xbrl_facts(xml_path)
view = build_xbrl_view(xml_path)
markdown = render_xbrl_markdown(view)
```

For an application-local label projection, walk `view["sections"][*]["rows"]` and copy the labels and values you explicitly want. Keep that flattening in the application so context-collapsing choices remain visible.

## Development

```bash
uv sync
uv run ruff check .
uv run pytest -q
npx --yes markdownlint-cli2 AGENTS.md README.md context/**/*.md
```

## Project docs

- Agent entrypoint: `AGENTS.md`
- Code map: `context/MAP.md`
- Durable tradeoffs: `context/DECISIONS.md`
- Imperative coding rules: `context/CONVENTIONS.md`
