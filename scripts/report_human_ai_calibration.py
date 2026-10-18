#!/usr/bin/env python3
"""Rebuild the Human–AI calibration report from stored responses and AI files.

The command does not write the canonical review queue.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claimledger.human_ai_calibration import (
    build_study,
    render_original_csv,
    render_report_json,
    render_report_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "benchmark" / "evaluation" / "human_ai_calibration"


def rendered(root: Path = ROOT) -> dict[str, str]:
    study = build_study(root)
    return {
        "report.json": render_report_json(study),
        "REPORT.md": render_report_markdown(study),
        "human_original_responses.csv": render_original_csv(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.write:
        parser.error("Pass --check or --write.")
    files = rendered()
    if args.write:
        for name, text in files.items():
            (STUDY / name).write_text(text, encoding="utf-8", newline="\n")
    if args.check:
        for name, text in files.items():
            path = STUDY / name
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                print(f"{name} does not match the study inputs.", file=sys.stderr)
                return 2
    study = json.loads(files["report.json"])
    original = study["original"]
    revised = study["after_feedback"]
    print(
        f"human_ai_agreement={original['agreements']}/{original['n']} "
        f"kappa={original['cohen_kappa']} "
        f"after_feedback={revised['agreements']}/{revised['n']} "
        f"gold_benchmark_released={study['integrity']['gold_benchmark_released']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
