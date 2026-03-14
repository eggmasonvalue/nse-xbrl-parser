# Changelog

## [Unreleased]
### Changed
- **Multi-Schema Validation Engine**: Completely replaced the hacky filename-based schema collision resolution. `parse_xbrl_file` now iterates through *all* matching schema files in the taxonomy archive, validates the instance document against each of them, and securely merges the output. This robustly bypasses NSE-introduced spelling inconsistencies and omitted elements without relying on namespace targeting.
- **Array Value Resolution**: Replaced string-concatenation for repeated XBRL tags. `parse_xbrl_file` now correctly aggregates multiple identical concepts (like `Name of allottee`) into a Python `List[str]` instead of a single comma-separated string.
- **Archive-Scoped Taxonomy Extraction**: `update_taxonomies.py` now extracts each NSE ZIP into its own stable archive directory before merging into `src/nse_xbrl_parser/taxonomies`. This prevents cross-archive overwrites of shared relative paths such as `core/in-capmkt.xsd`.
- **Namespace Compatibility Filtering**: `parse_xbrl_file` now skips entry-point schema candidates whose local relative imports already disagree with their declared namespaces, reducing noisy failed Arelle loads from damaged bundled releases.
### Fixed
- **Removed Raw XML Fallback**: `parse_xbrl_file` again fails fast when Arelle resolves zero facts. This keeps the parser taxonomy-driven and makes broken bundled schema dependencies visible instead of masking them with a sweep fallback.
- **Fraud Taxonomy Packaging**: Added the upstream `Taxonomy - Announcement for Fraud or Default` archive as an isolated bundled release so `in-capmkt-ent-2024-02-29.xsd` resolves against the correct `2024-02-29` core schemas.

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
