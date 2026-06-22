# CONVENTIONS

- Run `uv run ruff check .` before opening or updating a PR.
- Run `uv run pytest -q` before opening or updating a PR.
- Treat network-gated live NSE tests as skippable; keep skip behavior intact.
- Run `npx --yes markdownlint-cli2 AGENTS.md README.md context/**/*.md` before opening or updating a PR.
- Keep parser changes in `src/nse_xbrl_parser/parser.py` behavior-tested in `tests/test_parser.py`.
- Add new public API exports only through `src/nse_xbrl_parser/__init__.py`.
- Keep taxonomy index and stored release paths consistent with `src/nse_xbrl_parser/taxonomy_store.py`.
