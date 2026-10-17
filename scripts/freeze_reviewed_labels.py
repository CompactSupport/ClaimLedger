#!/usr/bin/env python3
"""Write an immutable freeze of human-reviewed labels.

Unreviewed author labels stay in the CSV and do not increase the reviewed count.
This command never marks a row as human-reviewed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claimledger.review import freeze_reviews, read_freeze

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path,
                        default=ROOT / "benchmark" / "candidates" / "review_queue.csv")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dataset-version", default=None)
    args = parser.parse_args()
    try:
        payload = freeze_reviews(
            args.queue,
            existing=read_freeze(args.out),
            dataset_version=args.dataset_version,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "reviewed_case_count="
        f"{payload['reviewed_case_count']} "
        "reviewed_subset_available="
        f"{payload['reviewed_subset_available']} "
        "eligible_for_final_approval="
        f"{payload['eligible_for_final_approval']} "
        "gold_benchmark_released="
        f"{payload['gold_benchmark_released']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
