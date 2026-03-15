# Code Conventions

Follows standard `code-quality` skill guidelines.

## Testing Conventions
- Live NSE download checks should prefer `curl` over in-process HTTP clients because the archive host is more reliable with browser-like `curl` settings in CI and local shells.
- Network-backed parser regressions must skip, not fail, when the remote host is unavailable or resets the connection. Parser assertions should only run after a successful download.
- The live regression suite targets specific filings (preferential issue listing, fraud announcement, notice of shareholders meeting, CIM appointment, alteration of capital) and asserts stable company/event details so regressions in those families are caught immediately.
