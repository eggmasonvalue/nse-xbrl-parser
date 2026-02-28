# nse-xbrl-parser

[![Built with uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://docs.astral.sh/uv/)

An open-source Python library to robustly parse National Stock Exchange (NSE) XBRL corporate announcements and automatically convert them into clean, human-readable JSON facts.

`nse-xbrl-parser` elegantly solves the infamous **"Missing Schema" / "Missing XSD"** problem. NSE XBRL filings often reference ancient taxonomy templates that have been wiped from their servers, or they `import` core schemas that are inexplicably omitted from the category-specific ZIP downloads.

This library acts as a 100% offline parsing engine. It resolves all these references against an internal, heavily pruned `taxonomies` archive. In-memory URI injection ensures that your filesystem and production Docker containers remain completely clean.

## 🚀 Features
- **Offline Resolution:** 44MB of historical NSE taxonomies bundled. No internet required during the `Arelle` schema validation phase.
- **Read-Only Safe:** Parses files directly from memory without `shutil.copytree` mutations; perfectly compliant with locked-down Python package installations.
- **Human-Readable Labels:** Preferentially maps obtuse XBRL QNames (e.g. `ns:Management`) back directly into their English equivalents (e.g. "Change in Management"). 
- **Agent/LLM Optimized:** Strictly typed, fully documented, and absolutely silent (suppresses noisy stdout warnings emitted by processing engines). Output JSON is perfect for fundamental analysis bots.

## 🛠️ Usage

Install using standard Python package managers:

```bash
uv add git+https://github.com/eggmasonvalue/nse-xbrl-parser.git
```

And parse a downloaded `*.xml` filing in Python:

```python
from nse_xbrl_parser import parse_xbrl_file
from pathlib import Path

# Provide the absolute path to your downloaded instance
filing_path = Path("SWIGGY_announcement_1.xml")

# The parser automatically detects the required schemas, performs validation,
# pulls the labels, and emits a clean JSON Dictionary
facts = parse_xbrl_file(filing_path)

print(facts)
# Example Out:
# {
#   "Reason for change": "Resignation",
#   "Date of appointment/cessation": "2024-05-15",
#   "Brief profile": "Jane Doe was leading..."
# }
```

## 🏗️ Architecture
Refer to the `.context/` living documentation directory for architectural specifics and design patterns enforcing this modular approach.
