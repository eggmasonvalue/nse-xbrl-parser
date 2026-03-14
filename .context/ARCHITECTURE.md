# Architecture

The `nse-xbrl-parser` library enforces a strict separation between the API entry-point, the dynamic XML rewrite phase, and the heavyweight Arelle validation engine.

## Module Structure

```mermaid
graph TD;
    API[parse_xbrl_file] --> Matcher[Schema Matcher]
    Matcher -->|Glob search| Vault[(taxonomies)]
    Vault -->|Archive-scoped directories| Releases[Per-ZIP release roots]
    Matcher --> Copier[Instance Copier]
    Copier -->|Copy to schema parent| Temp[Local XML instance]
    Temp --> Arelle[Arelle Validation Engine]
    Arelle --> JSON[Structured Fact Output]
```

## Data Flow
1. **Input**: A raw XML path is provided to `parse_xbrl_file()`.
2. **Schema Matching**: The parser uses simple regex to locate the target `href` inside the XML's `<link:schemaRef>` tag. It globs the local `taxonomies` directory to find matching entry-point XSDs across all preserved release roots.
3. **Archive Isolation**: The bundled taxonomy store keeps each downloaded NSE ZIP under its own root folder. Relative imports such as `../core/in-capmkt.xsd` therefore resolve within the source archive they came from instead of crossing into a globally overwritten shared `core/`.
4. **Compatibility Filter**: Before invoking Arelle, the parser drops candidate entry-points whose local relative imports already disagree with their declared namespaces.
5. **Locality Injection**: To preserve read-only constraints, the parser copies the input XBRL XML into the SAME directory as the discovered schema (as a `_temp_` file). This allows Arelle to resolve `..` relative paths natively.
6. **Validation**: The `arelle` engine is booted up silently to load this local temporary XML, ensuring all imports are found offline.
7. **Fact Extraction**: QName keys are resolved against the taxonomy into human-readable labels.
8. **Cleanup**: The temporary `_temp_` XML is immediately unlinked.

## Principles
* **Read-Only**: The module's root directory (`site-packages`) is never written to.
* **Silent**: Arelle generates no stdout/stderr logging noise, preserving AI agent context windows.
* **Typing**: Strict `typing` module compliance on endpoints.
