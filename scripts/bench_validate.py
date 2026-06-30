"""Benchmark Arelle validation cost for ``build_xbrl_view``.

Run:  uv run python scripts/bench_validate.py [--repeat N]

Compares wall-clock load+build time with ``validate=True`` (current default)
against ``validate=False`` using the in-repo synthetic announcement fixtures
(no network). Caching is bypassed (``use_cache=False``) so every iteration pays
the full Arelle load, which is the cost this benchmark isolates.

This exists to give the validation lever (RENDER_PLAN_v2 perf lever #2) a real
measurement instead of an assertion. It is a developer tool, not a test.
"""

from __future__ import annotations

import argparse
import statistics
import tempfile
import time
from pathlib import Path

from nse_xbrl_parser import build_xbrl_view, clear_view_cache

FRAUD_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2024-02-29/in-capmkt" xmlns:in-capmkt-ent="https://www.sebi.gov.in/xbrl/Announcement_For_Fraud_Or_Default/2024-02-29/in-capmkt/in-capmkt-ent" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <link:schemaRef xlink:type="simple" xlink:href="in-capmkt-ent-2024-02-29.xsd"/>
  <xbrli:context id="MainI">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">543386</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2026-03-02</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <in-capmkt:NameOfTheCompany contextRef="MainI">Fino Payments Bank Limited</in-capmkt:NameOfTheCompany>
  <in-capmkt:NSESymbol contextRef="MainI">FINOPB</in-capmkt:NSESymbol>
</xbrli:xbrl>
"""


def _time_runs(filing: Path, *, validate: bool, repeat: int) -> list[float]:
    timings: list[float] = []
    for _ in range(repeat):
        clear_view_cache()
        start = time.perf_counter()
        build_xbrl_view(filing, validate=validate, use_cache=False)
        timings.append(time.perf_counter() - start)
    return timings


def _report(label: str, timings: list[float]) -> float:
    best = min(timings)
    median = statistics.median(timings)
    print(
        f"{label:>16}: best={best * 1000:8.1f} ms  median={median * 1000:8.1f} ms  "
        f"runs={len(timings)}"
    )
    return median


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        filing = Path(tmp) / "fraud_case.xml"
        filing.write_text(FRAUD_FIXTURE, encoding="utf-8")

        # Warm up taxonomy/index caches so the comparison is steady-state.
        clear_view_cache()
        build_xbrl_view(filing, validate=True, use_cache=False)

        validate_true = _time_runs(filing, validate=True, repeat=args.repeat)
        validate_false = _time_runs(filing, validate=False, repeat=args.repeat)

    median_true = _report("validate=True", validate_true)
    median_false = _report("validate=False", validate_false)

    if median_false > 0:
        speedup = median_true / median_false
        delta = (median_true - median_false) * 1000
        print(
            f"\nvalidate=False is {speedup:.2f}x faster "
            f"({delta:+.1f} ms median saved per load)."
        )


if __name__ == "__main__":
    main()
