# nse-xbrl-parser

`nse-xbrl-parser` is a standalone, ultra-fast Python library designed to parse National Stock Exchange (NSE) XBRL filings and convert them into clean, human-readable JSON.

It addresses the fundamental issue with NSE XBRL parsing: the "missing XSD" problem, where filings reference core schemas that are missing from their specific category's ZIP file, or point to historical entry-points that have since disappeared from the internet.

## How It Works
It bundles an offline `taxonomies` archive where each taxonomy family stores historical releases directly under `taxonomies/<family>/<release_id>/...`. Each release carries its own sibling `core/` instead of relying on a single global `core/` folder. The updater appends only new content-distinct releases. When parsing an XBRL instance, the parser searches versioned family releases first, falls back to the current flat tree if needed, and copies the XML filing into the selected schema's parent directory as a temporary hidden file. This allows the Arelle parser to resolve the primary schema and all its relative dependencies natively via the filesystem.

## Purpose
Originally extracted from the KnowledgeLM project, `nse-xbrl-parser` is built to be an open-source, easily installable parser that any Python module can consume safely for automated financial data harvesting.
