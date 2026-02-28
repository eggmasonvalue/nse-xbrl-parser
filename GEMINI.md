# Context Artifacts Rule
.context/ artifacts are living documentation for the code. Keep .context/ artifacts in sync with code at all times.

**Artifact Definition:**
| File | Purpose | Update When |
|------|---------|-------------|
| [.context/OVERVIEW.md](.context/OVERVIEW.md) | Project scope and purpose | Dependencies, features change |
| [.context/ARCHITECTURE.md](.context/ARCHITECTURE.md) | Module structure and data flow. Use mermaid diagrams where sensible | Structure changes |
| [.context/CONVENTIONS.md](.context/CONVENTIONS.md) | Code patterns and standards | New patterns established |
| [.context/DESIGN.md](.context/DESIGN.md) | Feature status tracking | Features added/completed |
| [.context/CHANGELOG.md](.context/CHANGELOG.md) | Released changes | Any meaningful change |

**Definition of Done**: A task is complete ONLY when `.context/` artifacts reflect the code changes. Code without context updates is considered BROKEN.
