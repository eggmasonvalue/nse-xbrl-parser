# DECISIONS

## 2026-06-22 — Keep two parser outputs with a shared loader pipeline

Context: This library serves both announcement-style filings (single context, label-first usage) and financial statement filings (same concept repeated across periods, basis, and dimensions). A single output shape caused information loss for financial extraction.
Decision: Keep `parse_xbrl_file()` as a flat `{label: value | [values]}` API for announcement workloads, and keep `parse_xbrl_facts()` as the context-preserving fact-table API for financial workloads. Both paths share the same schema-resolution/Arelle loader (`_resolve_schema_candidates` + `_iter_loaded_models`) to stay DRY without changing behavior.
Tradeoff: Maintaining two public outputs increases API surface and tests, but avoids forcing breaking changes on announcement consumers while preserving complete context for financial analytics.
Status: active

## 2026-06-22 — Standardize on bundled offline taxonomy resolution

Context: NSE filings frequently reference historical or fragmented schema dependencies that are unavailable or inconsistent when resolved over the network.
Decision: Bundle the taxonomy store in-package and resolve entrypoints via `taxonomy_store` (`collect_versioned_schema_candidates` with indexed release metadata, then flat fallback). Parsing must work offline for taxonomy resolution.
Tradeoff: Package size and taxonomy maintenance cost increase, but parsing is deterministic and resilient to upstream host gaps.
Status: active

## 2026-06-22 — Keep IndiaInc-today XML announcement parsing out of this library

Context: IndiaInc-today includes a lightweight `xml.etree` parser for small announcement use cases.
Decision: Keep that lightweight parser app-local in IndiaInc-today; do not fold it into `nse-xbrl-parser`.
Tradeoff: Similar parsing logic exists in two codebases, but this library remains focused on Arelle-backed taxonomy-aware parsing and avoids coupling to app-specific shortcuts.
Status: active

## 2026-06-22 — Owner reconciliation required for version/tag drift (open)

Context: `pyproject.toml` and `src/nse_xbrl_parser/__init__.py` declare `0.2.0`, but tag `v1.0.0` exists and points to commit `61ca9b365ad1ef6b971f34711c72bb62a8822dbb`, which predates `parse_xbrl_facts`.
Decision: Record this as an active owner issue; do not retag or repin consumers in this housekeeping change.
Tradeoff: Release metadata remains temporarily inconsistent, but avoids accidental historical rewrite or publishing a misleading release from this docs-only PR.
Status: active (owner action required before next clean release tag including `parse_xbrl_facts`)

## 2026-06-24 — Backfill 2022 RPT taxonomy as an in-repo release derived from 2024 package

Context: Legacy standalone RPT filings (e.g., 30-SEP-2022 to 31-MAR-2024) reference `in-capmkt-ent-2022-03-31.xsd` with `http://` namespace URIs. The bundled taxonomy store had no `RelatedPartyTransactions` 2022 release, so schema candidate selection fell onto unrelated 2022 families and Arelle produced zero facts.
Decision: Add a dedicated `RelatedPartyTransactions/2022-03-31` release to the bundled taxonomy archive, derived from the known-good 2024 RPT package and rewritten to the 2022 entrypoint filename/date plus the legacy `http://.../in-capmkt` and `http://.../RelatedPartyTransactions/...` namespace URIs used by old filings.
Tradeoff: This is a compatibility backfill rather than a pristine upstream SEBI package mirror, but it restores deterministic offline parsing for old RPT instances without introducing network fetches or parser-side special cases.
Status: active
