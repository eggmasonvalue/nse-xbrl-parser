# Changelog

## [0.1.0] - 2026-02-28
### Added
- Migrated code and `taxonomies` from the main KnowledgeLM repository.
- Built a high-speed absolute `file://` URI rewrite mechanism to permit offline offline scheme resolution with `arelle`.
- Enabled the `parser.py` library to execute safely in read-only python environments without throwing `PermissionError` (e.g. system-level pip installs).
- Setup tests evaluating dynamic XSD loading criteria.
- Fully isolated `tempfile.TemporaryDirectory` injection.
