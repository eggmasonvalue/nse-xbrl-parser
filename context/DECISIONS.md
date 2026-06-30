# DECISIONS

## 2026-06-22 — Keep two parser outputs with a shared loader pipeline

Context: This library serves both announcement-style filings (single context, label-first usage) and financial statement filings (same concept repeated across periods, basis, and dimensions). A single output shape caused information loss for financial extraction.
Decision: Keep `parse_xbrl_file()` as a flat `{label: value | [values]}` API for announcement workloads, and keep `parse_xbrl_facts()` as the context-preserving fact-table API for financial workloads. Both paths share the same schema-resolution/Arelle loader (`_resolve_schema_candidates` + `_iter_loaded_models`) to stay DRY without changing behavior.
Tradeoff: Maintaining two public outputs increases API surface and tests, but avoids forcing breaking changes on announcement consumers while preserving complete context for financial analytics.
Status: superseded by 2026-06-30 — Replace flat parser with taxonomy-backed human view

## 2026-06-30 — Replace flat parser with taxonomy-backed human view

Context: The flat announcement parser collapsed repeated labels across contexts and made context loss the easiest public path. Consumers still need a readable human surface, including document-oriented markdown for RAG ingestion, but flattening labels into application columns is a consumer-specific collapse.
Decision: Delete the flat parser public surface. Expose `parse_xbrl_facts()` for lossless programmatic extraction, `build_xbrl_view()` for taxonomy/linkbase-backed structured human JSON, `render_xbrl_markdown()` for generic document rendering of that safe view, and `load_xbrl_model()` for one shared Arelle model load. Keep label-to-column flattening out of the library.
Tradeoff: Existing announcement consumers must migrate and own their local projection code, but the library no longer blesses context-collapsed dictionaries and still provides a generic human-readable path.
Status: active

## 2026-06-30 — Human view preserves context and avoids value transformation

Context: A readable XBRL view can accidentally reintroduce the same lossiness as a flat parser if it invents fiscal-year labels, merges standalone/consolidated or dimensional cells, rescales reported values, or returns nothing when presentation linkbases are absent.
Decision: Build the human view from taxonomy labels and linkbase relationships when present; derive period/basis columns from actual contexts; keep dimensional facts separated by explicit dimension sections; preserve reported values without rescaling; and fall back to period/basis/dimension grouping when presentation or calculation linkbases are unavailable.
Tradeoff: The default view is more structured than a one-row-per-label dictionary and may require callers to walk nested rows, but it remains readable while keeping context boundaries explicit.
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

## 2026-06-30 — Cache built views and keep validation conservative

Context: Arelle loading and DTS validation dominate runtime. The new human view needs facts, presentation, and calculation from one model, and batch consumers may request the same instance repeatedly.
Decision: Use `load_xbrl_model()` as the shared single-load path for view construction, keep `validate=True` as the default until fixture coverage proves a safe flip, tighten candidate selection with entrypoint target-namespace matching before Arelle retries, and cache built view dictionaries by file path, mtime, size, and view options. Cache view payloads, not live Arelle models.
Tradeoff: View caching returns defensive copies and uses bounded memory, which is less aggressive than model caching but avoids leaking large Arelle DTS/session objects. Keeping validation on leaves some speed on the table, but preserves current schema-selection and malformed-instance behavior.
Status: superseded by 2026-07-01 — Harden the view cache and keep a measured validation default

## 2026-07-01 — Indent nested markdown rows with ASCII spaces, not `&nbsp;`

Context: Consumers reported "nbsp/weird characters" in rendered markdown. Testing real filings (HDFCBANK, ESTER via the KnowledgeLM CLI) showed the source text was clean; the only `&nbsp;` reaching consumers was our own nested-row indentation markup (`&nbsp;&nbsp;` x depth) in `_append_markdown_table`. Full HTML-aware renderers show it as spaces, but the actual consumers (LLM/RAG and plaintext pipelines) surface the literal `&nbsp;` token as noise.
Decision: Indent nested table rows with plain ASCII spaces via `INDENT_UNIT`. Do not add speculative Unicode normalization for hypothetical dirty source text — real NSE data did not exhibit raw no-break/zero-width characters, so that layer was reverted as unnecessary maintenance surface.
Tradeoff: ASCII-space indentation may collapse visually in some HTML table renderers, but the primary consumers are LLM/RAG/plaintext pipelines where leading spaces are preserved and `&nbsp;` was surfacing as noise.
Status: active

## 2026-07-01 — Harden the view cache and keep a measured validation default

Context: The first performance pass added an in-process `build_xbrl_view` cache, a `validate` option, and an entrypoint target-namespace candidate filter, but left gaps: the cache was a process-global `OrderedDict` mutated without a lock and exposed no public clear/disable, the `validate` default was chosen without a measurement, and the candidate filter's effect was unverified. Batch consumers (ingestion harvesters) can call `build_xbrl_view` concurrently.
Decision: Serialize all cache access behind a module lock, add `build_xbrl_view(..., use_cache=False)` to bypass the cache, and add a public `clear_view_cache()` (exported) so callers and tests never touch the private `_VIEW_CACHE`. Keep `validate=True` as the default, now backed by a benchmark and an output-parity guard. `parse_xbrl_facts` keeps its multi-model merge semantics while `load_xbrl_model`/`build_xbrl_view` bind to the single first viable candidate; this divergence is documented in both docstrings.
Measurement: `scripts/bench_validate.py` on the bundled synthetic announcement fixture shows `validate=False` is ~5x faster (~1.0 s median saved per cold load: ~1264 ms -> ~245 ms). `test_validate_modes_produce_equivalent_human_view` asserts title/columns/label-value parity across both modes on that fixture. The default stays `True` because the parity proof does not yet cover linkbase-bearing financial statements or malformed instances, where validation still aids schema-candidate selection and error surfacing; flipping the global default needs that broader fixture coverage first.
Candidate filter: the entrypoint target-namespace pre-filter narrows the ambiguous announcement entrypoint `in-capmkt-ent-2022-06-30.xsd` from 28 candidates to 3 — identical to the existing taxonomy-index namespace pass. It is kept as a cheap, ground-truth pre-filter (it reads the schema file's own `targetNamespace` rather than trusting index metadata, so it stays correct if the index drifts). The end-to-end resolution of that ambiguous entrypoint is guarded by `test_parse_qip_listing_includes_allottee_category_fields`.
Tradeoff: Locking adds negligible contention for the dominant Arelle-load cost, and keeping the redundant-but-robust candidate pre-filter costs one cheap per-file XML read only when more than one candidate survives. The conservative `validate=True` default forgoes the measured ~5x win until correctness parity is proven on the harder fixture classes.
Status: active

## 2026-07-01 — Two performance levers intentionally NOT taken (revisit tripwire)

Context: Arelle DTS load + validation dominate runtime, so future performance work will be tempted by the two largest-looking levers again. Both look attractive in isolation and both are wrong as global defaults. This entry exists so a later agent/human does not re-walk and re-break this. Measurements and parity guards live in the prior 2026-07-01 cache/validation decision.

Rejected lever A — flipping the default to `validate=False`.

- Apparent win: ~5x faster (~1.0s saved per cold load on the synthetic announcement fixture; see `scripts/bench_validate.py`).
- Why rejected as a default: Arelle always loads the DTS, linkbases, and facts regardless of the flag; validation is only the post-load conformance pass. Turning it off does NOT speed up extraction of clean filings' data — it removes correctness guards that matter on the messy tail this library exists for. Specifically: (1) schema-candidate selection gets less robust — `_iter_loaded_models` accepts the first candidate DTS that loads with facts, and validation is part of what rejects a wrong/incompatible candidate; without it a wrong taxonomy interpretation can be accepted and the ENTIRE view (labels, structure, title) comes from the wrong DTS — a silent whole-output failure; (2) malformed instances (bad context/unit refs, wrong datatypes, invalid typed dimensions — common in historical NSE data) get silently loaded as if valid instead of erroring or being flagged; (3) we lose a loud-failure signal, and silent wrong financials are worse than a raised error.
- Standing rule: keep `validate=True` as the default. `validate=False` stays a per-call opt-in for callers who KNOW their inputs are clean. Do not flip the global default until output parity is proven across the hard fixture classes, not just clean announcements: linkbase-bearing financial statements, deliberately malformed instances, and multi-candidate (ambiguous) filings. A green parity test on one clean fixture is necessary but nowhere near sufficient.

Rejected lever B — merging facts across all candidate models into `build_xbrl_view`.

- Apparent win: fact-set parity with `parse_xbrl_facts` (which already unions+dedupes facts across every candidate that loads), and maximal recall on ambiguous filings.
- Why rejected for the view: a "candidate model" is a separate, independent DTS — a different taxonomy interpretation of the same instance. Fact values are identical across candidates, but the view's structure (presentation tree, calculation relationships, preferred labels, role URIs, title, columns) is a property of ONE DTS and cannot be coherently merged. Merging facts but keeping structure from a single DTS yields incoherent output: merged-in facts have no node in the chosen presentation tree (they drop to the flat fallback, possibly label-less), and the calc `checks` get computed against a fact set the chosen calculation linkbase never knew about. Merging the structure itself is impossible (conflicting roles/labels/order). It also forces loading ALL candidates, partly undoing the candidate-tightening lever.
- Why the divergence is acceptable: this only ever differs when >1 candidate loads with facts (the rare ambiguous case); in the common single-candidate case merge and first-only are byte-identical. For raw facts, union/dedupe is lossless and correct, so `parse_xbrl_facts` keeps merging. For the structured view, a coherent single-DTS rendering is worth more than maximal recall.
- Standing rule: `build_xbrl_view`/`load_xbrl_model` bind to the single first viable candidate; `parse_xbrl_facts` keeps its multi-model merge. Do not "fix" the divergence by merging candidates into the view. If recall on ambiguous filings ever becomes a real, evidenced problem, the only acceptable shape is a hybrid (one deterministic primary DTS for structure + unioned raw cells with extras in the flat fallback, and `checks` explicitly scoped to the primary model) — not a structure merge, and only with fixtures proving multi-candidate filings actually occur.

Status: active
