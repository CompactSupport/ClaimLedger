#!/usr/bin/env python3
"""Run the offline semantic-pilot gate.

``--check`` executes mock integration checks only. It does not launch a model,
and a passing mock is not a semantic-model evaluation result. A subprocess
command used by tests is not an operating-system sandbox and is not model
execution.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from claimledger.semantic_pilot import offline_mock_checks

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run offline mock checks. This command does not start a model.",
    )
    args = parser.parse_args(argv)
    if not args.check:
        print(
            "Pass --check for the offline mock gate. A subscription run is scripts/run_adjudicated_subset.py --run.",
            file=sys.stderr,
        )
        return 2
    workspace = Path(tempfile.mkdtemp(prefix="claimledger-pilot-check-"))
    try:
        report = offline_mock_checks(workspace, ROOT)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    if report["failures"]:
        for item in report["failures"]:
            print(item, file=sys.stderr)
        return 1
    print("offline_mock_checks=passed")
    print("real_model_execution=not_started")
    print("api_key_fallback=refused")
    print("os_sandbox=false")
    print("mock_results_are_model_evaluation=false")
    print(f"paid_model_calls={report['paid_model_calls']}")
    print(f"human_labels_synthesized={str(report['human_labels_synthesized']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
