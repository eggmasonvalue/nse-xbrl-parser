# Architecture

```mermaid
graph TD;
    API[parse_xbrl_url] --> Parser[Arelle XBRL Engine]
    Parser --> Root[Golden Taxonomy Local Source]
    Parser --> JSON[Structured Fact Output]
```
