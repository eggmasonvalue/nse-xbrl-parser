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
