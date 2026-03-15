# Design & Features

## Completed Features
- **Standalone API**: Simple, single-function `parse_xbrl_file` endpoint.
- **Versioned Family Storage**: `taxonomy_store.py` now stores releases directly under `taxonomies/<family>/<release_id>/...`, with each release carrying its own `core/` and optional `META-INF/`.
- **Append-Only Updater**: `update_taxonomies.py` now downloads and extracts each NSE ZIP in isolation, fingerprints detected release units using `family + core + file contents`, and only installs genuinely new releases for that family.
- **Read-Only Compliance**: Safe for Docker containers and system-wide pip installs; the parser relies on a temporary colocated XML copy rather than rewriting installed package files.
- **Arelle Integration**: Wrapped the complex `arelle` initialization to run silently and efficiently process the facts array against label stores.
- **Human Readable output**: Prioritize standard and verbose english labels over obtuse XML QNames.
- **Intelligent Multi-Schema Merging (Resolved Technical Debt)**: Addressed the issue where identical root filenames (e.g. `in-capmkt-ent-2022-06-30.xsd`) inside the NSE archive caused Arelle validations to fail. We iterate and run Arelle against *all* matching XSD schemas across the different taxonomy directories, merging the parsed facts into a single unified result.
- **Fast Indexed Discovery**: `collect_versioned_schema_candidates` leverages the `index.json` manifest to locate matching entry points instantly without executing slow recursive filesystem globs.
- **Namespace-Based Disambiguation**: To optimize the multi-schema merging strategy, the parser now extracts namespaces directly from the incoming XBRL instance. It compares these against the `target_namespaces` and `imported_core_namespaces` stored in `index.json`, aggressively filtering out colliding but irrelevant schemas before they trigger redundant and expensive Arelle evaluations.
- **Versioned-First Resolution**: `parse_xbrl_file` searches versioned family releases before consulting the flat tree, so release-local `core/` folders win over the compromised shared flat `core/`.
- **Strict Local Import Validation**: Candidate entry-points are only considered compatible when all local relative imports exist and their `targetNamespace` values match the declared `xsd:import namespace`.
- **Type-safe Array Handling (Resolved Technical Debt)**: When duplicate facts (like `NameOfAllottee`) appear, the parser now natively stores them as `List[str]` in the output dictionary instead of dissolving the array boundaries via string concatenation.
- **Fail-Fast Validation**: If Arelle cannot resolve any facts for the selected schema set, the parser raises instead of falling back to a raw XML sweep. Broken bundled taxonomies are treated as packaging defects that must be fixed at the source.
- **Live Filing Regression Coverage**: `tests/test_parser.py` now includes `curl`-based integration regressions for several NSE filings (preferential issue listing, fraud/default announcement, notice of shareholders meeting, CIM appointment, and alteration of capital). Each regression verifies that the corresponding bundled taxonomy still yields the expected human-readable facts when parsing the live XML.

### Current Storage Strategy
- **No Shared Global Core**: A single top-level `taxonomies/core` is not treated as authoritative anymore. Releases are identified and stored with their own `core/`.
- **One Release ID Per Family**: If a ZIP contains `QIP_IP` and `QIP_Listing`, each family gets its own independent `release_id` even if both share the same source archive.
- **Content Identity Over ZIP Names**: Release identity is derived from family contents plus that family's paired `core/`. ZIP filenames are retained only as provenance metadata in the index.

## Future / Planned
- Detection Heuristics: improve release-unit discovery for archives that currently produce `0 release units` because their entry-point naming deviates from the current heuristics.
- Ranking: teach the parser to rank multiple valid versioned releases within a family more deterministically than simple filesystem order.
