# Design & Features

## Completed Features
- **Standalone API**: Simple, single-function `parse_xbrl_file` endpoint.
- **Taxonomy Bundle**: Consolidated, fully merged historical NSE XBRL taxonomies. Includes Board Outcomes, Reg30, Shareholder Meetings, and Personnel schemas. (Bloated Excel files aggressively pruned).
- **In-Memory Offline Resolution**: Replaces massive and slow `shutil.copytree` directory cloning with high-speed dynamic URI injections via `re.sub()`, solving missing schema dependencies.
- **Read-Only Compliance**: Safe for Docker containers and system-wide pip installs, heavily relying on `tempfile.TemporaryDirectory`.
- **Arelle Integration**: Wrapped the complex `arelle` initialization to run silently and efficiently process the facts array against label stores.
- **Human Readable output**: Prioritize standard and verbose english labels over obtuse XML QNames.

## Future / Planned
- Automation (`CI/CD`): Implement GitHub actions to periodically scrape the NSE taxonomy definitions, aggregate new schemas into `taxonomies`, and automatically publish new PyPI versions.
- Handle Version 2 adoption constraints.

## Technical Debt and Workarounds

The underlying taxonomy files provided by the NSE and the XML instance files submitted by the companies frequently contain major data inconsistencies, spelling errors, and un-taxonomized fields. Because of the severe time constraints imposed during the v0.1 deliverables, a number of "hacky" fallback mechanisms and non-production grade string checks were introduced to guarantee data extraction.

1. **Intelligent Schema Resolution Prefixing (`parser.py`)**
   - **Issue:** Multiple independent taxonomies (ADR, QIP, PREF, etc.) share identical root filenames (e.g. `in-capmkt-ent-2022-06-30.xsd`) inside the NSE archive. `Arelle` loads schemas by filename, and seemingly validations all documents against the very first matching XSD it finds, aggressively dropping elements like `PercentageOfTotalIssueSize`.
   - **Workaround:** We explicitly read the target XML file prefix (`QIP_LS_...`) to logically infer and forcefully route the execution to a specific taxonomy directory instead of letting Arelle properly parse the schema tree natively. This arbitrarily couples the parser tightly to NSE file naming conventions rather than robust XML namespace routing.

2. **String Concatenation for Repeated XBRL Arrays**
   - **Issue:** `Arelle` yields a flat list of `model_xbrl.facts`. When elements like `NameOfAllottee` appear multiple times sequentially to represent an array layout, mapping them directly into a Python `Dict[str, Any]` naturally overwrites previous entries.
   - **Workaround:** If a label already exists in the dictionary, the parser brutally concatenates the new value via a comma-delimited string natively `f"{parsed_data[label]}, {fact.value}"`. This breaks type-safety, dissolving the native array boundaries and forcing downstream consumers to deserialize strings on their own.

3. **Aggressive XML Sweep Fallback**
   - **Issue:** `Arelle` silently drops fields like `CategoryOfAllotees` outright because of inconsistencies and spelling errors by the NSE between their XML instance files and their compiled local dictionary schemas (e.g. "te" vs "tte").
   - **Workaround:** Any valid XML text property entirely ignored/dropped by Arelle during runtime is automatically rescued at the very end of execution natively via a fast `xml.etree.ElementTree` iteration loop. It uses regex `re.sub` to blindly format the XML tags into capitalized human labels. It unconditionally permits duplicate values without understanding schema constraints.

### Future Production-Grade Recommendations
- Build a robust graph of the XSD taxonomy namespaces to logically route Arelle validations independently of file prefixes.
- Deprecate flat dict parsing and instantiate standard typed Pydantic models with true `List[str]` payload fields for arrays.
- Re-compile the raw NSE XBRL `taxonomies` directory to patch and fix the underlying spelling discrepancies mathematically instead of rescuing dropped data in Python at runtime.
