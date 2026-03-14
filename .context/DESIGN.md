# Design & Features

## Completed Features
- **Standalone API**: Simple, single-function `parse_xbrl_file` endpoint.
- **Taxonomy Bundle**: Consolidated, fully merged historical NSE XBRL taxonomies. Includes Board Outcomes, Reg30, Shareholder Meetings, and Personnel schemas. (Bloated Excel files aggressively pruned).
- **In-Memory Offline Resolution**: Replaces massive and slow `shutil.copytree` directory cloning with high-speed dynamic URI injections via `re.sub()`, solving missing schema dependencies.
- **Read-Only Compliance**: Safe for Docker containers and system-wide pip installs, heavily relying on `tempfile.TemporaryDirectory`.
- **Arelle Integration**: Wrapped the complex `arelle` initialization to run silently and efficiently process the facts array against label stores.
- **Human Readable output**: Prioritize standard and verbose english labels over obtuse XML QNames.
- **Intelligent Multi-Schema Merging (Resolved Technical Debt)**: Addressed the issue where identical root filenames (e.g. `in-capmkt-ent-2022-06-30.xsd`) inside the NSE archive caused Arelle validations to fail. We iterate and run Arelle against *all* matching XSD schemas across the different taxonomy directories, merging the parsed facts into a single unified result.
- **Archive-Scoped Taxonomy Packaging**: Each downloaded NSE ZIP is now extracted and copied under its own stable archive directory. This preserves sibling `core/` dependencies for that release and prevents unrelated archives from overwriting `core/in-capmkt.xsd` or `core/in-capmkt-types.xsd`.
- **Namespace Compatibility Prefilter**: The parser now inspects each candidate entry-point's local relative imports before invoking Arelle. Candidates whose imported file namespaces do not match their declared `xsd:import namespace` values are skipped early.
- **Type-safe Array Handling (Resolved Technical Debt)**: When duplicate facts (like `NameOfAllottee`) appear, the parser now natively stores them as `List[str]` in the output dictionary instead of dissolving the array boundaries via string concatenation.
- **Fail-Fast Validation**: If Arelle cannot resolve any facts for the selected schema set, the parser raises instead of falling back to a raw XML sweep. Broken bundled taxonomies are treated as packaging defects that must be fixed at the source.

### Design Decisions: Multi-Schema Merging vs. Namespace Routing
When resolving the Intelligent Schema Resolution issue, two approaches were evaluated:
- **Option A (Namespace Matching)**: Extract the XML namespace (e.g. `xmlns:in-capmkt-ent=...`) and locate the exact taxonomy `.xsd` that contains the matching `targetNamespace`. Validation is run only once against that single file.
  - *Tradeoffs*: Fast. However, if a required fact (like `PercentageOfTotalIssueSize`) is accidentally misspelled or entirely omitted by the NSE inside that specific category's `.xsd` file, the data will be silently dropped.
- **Option B (Multi-Schema Merging)**: Iterate through *all* taxonomy directories that contain a file matching the `schemaRef`. Validate the instance XML against every match, and merge the successful results.
  - *Tradeoffs*: Slower (approx. 2.5-3.5 seconds overhead to validate multiple schemas vs a single one), but vastly more robust. It successfully extracts facts across disparate and sometimes broken schemas by pooling the available dictionary definitions.

We deployed **Option B**, as the fundamental purpose of this parser is maximizing robust extraction against highly inconsistent NSE filings. The aggressive multi-schema sweep cleanly obsoleted the need for the dangerous `ElementTree` fallback hacks.

## Future / Planned
- Automation (`CI/CD`): Implement GitHub actions to periodically scrape the NSE taxonomy definitions, aggregate new schemas into `taxonomies`, and automatically publish new PyPI versions.
- Handle Version 2 adoption constraints.
- Build a namespace index over the archive-scoped taxonomy store to prune obviously incompatible entry-point matches before invoking Arelle.
- Normalize bundled `core` taxonomy versions so Arelle can validate 2024+ filings without namespace mismatches.
