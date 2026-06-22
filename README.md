# nse-xbrl-parser

[![Built with uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://docs.astral.sh/uv/)

`nse-xbrl-parser` is an offline-taxonomy NSE XBRL parser library for Python.

It is built for the common NSE failure mode where filings reference historical or incomplete taxonomy dependencies. The package ships a bundled taxonomy archive and resolves schemas locally, so Arelle validation and fact extraction do not depend on live taxonomy hosting.

## Install

```bash
uv add git+https://github.com/eggmasonvalue/nse-xbrl-parser.git
```

## Public API

- `parse_xbrl_file(path)`
  - Returns a flat announcement-oriented dictionary: `{label: value | [values]}`.
- `parse_xbrl_facts(path)`
  - Returns a context-preserving fact table (`list[dict]`) with one row per concept/value/context/unit/decimals/period/basis/dimensions.

Both APIs reuse the same schema resolution + Arelle loading pipeline.

## Usage

```python
from pathlib import Path
from nse_xbrl_parser import parse_xbrl_file, parse_xbrl_facts

xml_path = Path("filing.xml")

announcement_facts = parse_xbrl_file(xml_path)
financial_facts = parse_xbrl_facts(xml_path)
```

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
