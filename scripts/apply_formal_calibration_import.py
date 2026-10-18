#!/usr/bin/env python3
"""Write or check the formal two-reviewer calibration import.

The author ``expected`` column is preserved. This does not release a gold benchmark.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claimledger.human_ai_calibration import assemble_formal_review

ROOT = Path(__file__).resolve().parents[1]


def rendered(root: Path = ROOT) -> dict[str, str]:
    payload = assemble_formal_review(root)
    return {
        "benchmark/candidates/review_queue.csv": payload["queue_csv"],
        "benchmark/evaluation/formal_review/response_sheet_steven.csv": payload["sheet_steven"],
        "benchmark/evaluation/formal_review/response_sheet_david.csv": payload["sheet_david"],
        "benchmark/evaluation/formal_review/adjudications.json": payload["adjudications_json"],
        "benchmark/evaluation/formal_review/approval.json": payload["approval_json"],
    }, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.write:
        parser.error("Pass --check or --write.")
    files, payload = rendered()
    if args.write:
        for relative, text in files.items():
            path = ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if args.check:
        for relative, text in files.items():
            path = ROOT / relative
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                print(f"{relative} does not match the formal review.", file=sys.stderr)
                return 2
    print(
        f"paired_cases={payload['paired_cases']} "
        f"sheet_disagreements={len(payload['sheet_disagreements'])} "
        f"gold_benchmark_released={payload['gold_benchmark_released']} "
        f"independence_verified={payload['independence_verified']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
