# Changelog

## [Unreleased]
### Changed
- **Multi-Schema Validation Engine**: Completely replaced the hacky filename-based schema collision resolution. `parse_xbrl_file` now iterates through *all* matching schema files in the taxonomy archive, validates the instance document against each of them, and securely merges the output. This robustly bypasses NSE-introduced spelling inconsistencies and omitted elements without relying on namespace targeting.
- **Array Value Resolution**: Replaced string-concatenation for repeated XBRL tags. `parse_xbrl_file` now correctly aggregates multiple identical concepts (like `Name of allottee`) into a Python `List[str]` instead of a single comma-separated string.
- **Removed Fallback Sweep**: Completely removed the raw `xml.etree.ElementTree` fallback rescue loop. The multi-schema merging engine guarantees sufficient coverage to natively rely on Arelle's validation logic.

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
