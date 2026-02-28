# nse-xbrl-parser

`nse-xbrl-parser` is a standalone, ultra-fast Python library designed to parse National Stock Exchange (NSE) XBRL filings and convert them into clean, human-readable JSON. 

It addresses the fundamental issue with NSE XBRL parsing: the "missing XSD" problem, where filings reference core schemas that are missing from their specific category's ZIP file, or point to historical entry-points that have since disappeared from the internet.

## How It Works
It bundles an offline `taxonomies` archive that preserves the exact directory structure of the National Stock Exchange filings. When parsing an XBRL instance, the parser locates the required schema and copies the XML filing into that schema's parent directory as a temporary hidden file. This allows the Arelle parser to resolve the primary schema and all its relative dependencies (e.g., `../core/types.xsd`) natively via the filesystem, ensuring 100% offline accuracy even in read-only installations.

## Purpose
Originally extracted from the KnowledgeLM project, `nse-xbrl-parser` is built to be an open-source, easily installable parser that any Python module can consume safely for automated financial data harvesting.
