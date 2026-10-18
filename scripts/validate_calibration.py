#!/usr/bin/env python3
"""Validate the 30-case calibration sheets and write an agreement report.

The command reads reviewer sheets. It does not write the canonical review queue
and it does not invent reviews.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claimledger.calibration import report_for_repository

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "benchmark" / "evaluation" / "reports" / "calibration_agreement.json"


def render(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.write:
        parser.error("Pass --check or --write.")
    report = report_for_repository(ROOT)
    text = render(report)
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(text, encoding="utf-8", newline="\n")
    if args.check and (not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != text):
        print("Calibration report does not match the sheets.", file=sys.stderr)
        return 2
    print(
        f"paired_cases={report['paired_cases']} "
        f"cohen_kappa={report['cohen_kappa']} "
        f"queue_updated={report['queue_updated']} "
        f"gold_benchmark_released={report['gold_benchmark_released']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
