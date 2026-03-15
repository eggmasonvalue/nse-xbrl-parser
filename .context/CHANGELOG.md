# Changelog

## [Unreleased]
### Added
- **Live NSE Regression Tests**: Added parser integration tests that download several representative NSE filings (`PREF_ISSUE_LS_1634111_10032026122945_WEB.xml`, the related fraud/default announcement, the shareholders-meeting notice, a CIM appointment, and an alteration-of-capital announcement) via `curl`, parse them with the bundled taxonomies, and verify key facts while skipping cleanly if the NSE host is unavailable.
### Changed
- **Arelle API Migration**: Refactored the `arelle` engine integration to support breaking changes in `arelle-release`. Replaced deprecated direct `Cntlr.Cntlr()` usage with the new `arelle.api.Session` context manager and `arelle.RuntimeOptions`.
- **Fast Indexed Schema Discovery**: Optimized `collect_versioned_schema_candidates` to look up schemas using the `index.json` manifest instead of recursively globbing the filesystem, vastly reducing discovery overhead.
- **Namespace-Based Disambiguation**: Added `_get_instance_namespaces` to extract namespaces from the incoming XBRL instance. The parser now filters matching schemas by comparing their `target_namespaces` and `imported_core_namespaces` against the instance's declared namespaces. This fixes extreme slowness caused by redundant Arelle evaluation when a single schema reference collides across multiple taxonomy families (e.g., `in-capmkt-ent-2022-06-30.xsd` matching 10 different families).
- **Multi-Schema Validation Engine**: Completely replaced the hacky filename-based schema collision resolution. `parse_xbrl_file` now iterates through *all* matching schema files in the taxonomy archive, validates the instance document against each of them, and securely merges the output. This robustly bypasses NSE-introduced spelling inconsistencies and omitted elements without relying on namespace targeting.
- **Array Value Resolution**: Replaced string-concatenation for repeated XBRL tags. `parse_xbrl_file` now correctly aggregates multiple identical concepts (like `Name of allottee`) into a Python `List[str]` instead of a single comma-separated string.
- **Versioned Taxonomy Storage**: Added `src/nse_xbrl_parser/taxonomy_store.py` and switched taxonomy storage to `src/nse_xbrl_parser/taxonomies/<family>/<release_id>/...`, with one release ID per family and no shared authoritative top-level `core/`.
- **Append-Only Taxonomy Updates**: `scripts/update_taxonomies.py` now downloads each NSE ZIP in isolation, discovers family release units, fingerprints `family + core + contents`, and appends only genuinely new releases instead of overwriting flattened folders.
- **Versioned-First Parsing**: `parse_xbrl_file` now searches versioned family releases before the flat taxonomy tree and requires all local relative imports to exist and namespace-match before a candidate schema is considered compatible.
- **Workflow Verification**: The taxonomy update GitHub workflow now syncs the project environment and runs `pytest` after refreshing taxonomies, preventing scheduled commits from publishing a broken bundle.
### Fixed
- **Python 3.12 Compatibility**: Updated `arelle-release` to `>=2.39.1` to fix a `MutableSet` import error in `arelle/PythonUtil.py` that occurred on Python 3.10+.
- **Removed Raw XML Fallback**: `parse_xbrl_file` again fails fast when Arelle resolves zero facts. This keeps the parser taxonomy-driven and makes broken bundled schema dependencies visible instead of masking them with a sweep fallback.
- **Fraud Taxonomy Packaging**: Added the upstream `Taxonomy - Announcement for Fraud or Default` archive as an isolated bundled release so `in-capmkt-ent-2024-02-29.xsd` resolves against the correct `2024-02-29` core schemas.
- **QIP Listing Coverage**: Refreshing taxonomies now brings in the latest archive-scoped QIP bundle, restoring missing facts such as `Category of allotees`, `Percentage of total issue size`, `Date of BID opening`, and `Relavant date`.

## [0.2.0] - 2026-02-28
### Fixed
- **Robust Schema Resolution**: Replaced the fragile `file:///` URI injection strategy with a native directory-relative resolution. The parser now temporarily copies the XBRL XML into the schema's own directory, allowing Arelle to follow relative imports (e.g. `../core/...`) natively.
- **Preserved Taxonomy Structure**: Fixed the `update_taxonomies.py` script to maintain the exact directory hierarchy from NSE ZIPs. This prevents "shadowing" of core schemas across different filing categories.
- **Cleanup**: Purged 160+ broken/shadowed schema files from the package root.

## [0.1.0] - 2026-02-28
### Added
- Migrated code and `taxonomies` from the main KnowledgeLM repository.
- Built a high-speed absolute `file://` URI rewrite mechanism to permit offline scheme resolution with `arelle`.
- Enabled the `parser.py` library to execute safely in read-only python environments without throwing `PermissionError` (e.g. system-level pip installs).
- Setup tests evaluating dynamic XSD loading criteria.
- Fully isolated `tempfile.TemporaryDirectory` injection.
