#!/usr/bin/env python3
"""Write an immutable freeze of human-reviewed labels.

Unreviewed author labels stay in the CSV and do not increase gold_count.
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
    args = parser.parse_args()
    try:
        payload = freeze_reviews(args.queue, existing=read_freeze(args.out))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"reviewed_case_count={payload['reviewed_case_count']} "
        f"gold_benchmark_ready={payload['gold_benchmark_ready']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
