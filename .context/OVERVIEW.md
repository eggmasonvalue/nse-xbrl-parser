# nse-xbrl-parser

`nse-xbrl-parser` is a standalone, ultra-fast Python library designed to parse National Stock Exchange (NSE) XBRL filings and convert them into clean, human-readable JSON. 

It addresses the fundamental issue with NSE XBRL parsing: the "missing XSD" problem, where filings reference core schemas that are missing from their specific category's ZIP file, or point to historical entry-points that have since disappeared from the internet.

## How It Works
It bundles an offline `taxonomies` archive (a heavily compressed consolidation of all historical NSE taxonomies). When parsing an XBRL instance, it dynamically injects an absolute `file://` URI into the XML `schemaRef` in-memory. This allows the Arelle parser to resolve schemas with 100% offline accuracy in a read-only environment without polluting the local filesystem.

## Purpose
Originally extracted from the KnowledgeLM project, `nse-xbrl-parser` is built to be an open-source, easily installable parser that any Python module can consume safely for automated financial data harvesting.
