# Architecture

The `nse-xbrl-parser` library enforces a strict separation between the API entry-point, the dynamic XML rewrite phase, and the heavyweight Arelle validation engine.

## Module Structure

```mermaid
graph TD;
    API[parse_xbrl_file] --> Matcher[Schema Matcher]
    Matcher -->|Versioned-first lookup| Versioned[(taxonomies/<family>/<release_id>)]
    Matcher -->|Flat fallback| Flat[(taxonomies current flat tree)]
    Updater[update_taxonomies.py] --> Versioned
    LiveTests[tests/test_parser.py live curl regressions] --> API
    Versioned --> Index[index.json]
    Matcher --> Copier[Instance Copier]
    Copier -->|Copy to schema parent| Temp[Local XML instance]
    Temp --> Arelle[Arelle Validation Engine]
    Arelle --> JSON[Structured Fact Output]
```

## Data Flow
1. **Input**: A raw XML path is provided to `parse_xbrl_file()`.
2. **Schema Matching**: The parser locates the target `href` inside the XML's `<link:schemaRef>` tag and extracts all namespaces declared in the instance document. It searches versioned family releases first by looking up the `href` in `index.json` to quickly find candidates.
3. **Disambiguation**: To prevent extreme slowness when a schema reference collides across multiple taxonomy families, the parser filters candidate schemas by strictly checking if their `target_namespaces` or `imported_core_namespaces` (as stored in `index.json`) match the instance's declared namespaces.
4. **Versioned Release Store**: `src/nse_xbrl_parser/taxonomy_store.py` fingerprints release units by `family + core + contents` and writes them under `taxonomies/<family>/<release_id>/...`. `index.json` records family, fingerprint, provenance, and stored path.
5. **Updater Path**: `scripts/update_taxonomies.py` downloads fresh NSE ZIPs, extracts each archive in isolation, detects family release units, and appends only self-contained releases whose family+fingerprint pair is not already present.
6. **Compatibility Filter**: Before invoking Arelle, the parser drops candidate entry-points whose local relative imports are missing or disagree with their declared namespaces.
7. **Locality Injection**: The parser copies the input XBRL XML into the SAME directory as the discovered schema (as a `_temp_` file). This allows Arelle to resolve `..` relative paths natively.
8. **Validation and Fact Extraction**: The `arelle` engine loads the temporary XML, resolves labels, and emits unique facts. If multiple compatible schemas survive the namespace filtering, it evaluates against all of them and securely merges the output.
9. **Cleanup**: The temporary `_temp_` XML is immediately unlinked.
10. **Live Regression Tests**: `tests/test_parser.py` can fetch multiple NSE filings (preferential issue listing, fraud/default announcement, notice of shareholders meeting, CIM, and alteration of capital) with `curl`, feed each into `parse_xbrl_file()`, and assert stable facts. Transport failures are treated as environmental skips so the parser is only evaluated after a successful download.

## Principles
* **Read-Only**: The module's root directory (`site-packages`) is never written to.
* **Silent**: Arelle generates no stdout/stderr logging noise, preserving AI agent context windows.
* **Typing**: Strict `typing` module compliance on endpoints.
