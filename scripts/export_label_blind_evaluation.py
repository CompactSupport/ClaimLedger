#!/usr/bin/env python3
"""Write or check the label-blind evaluation export.

The canonical candidate files are read and left unchanged.
``--agent-dir`` copies only the model view to a directory outside this repository.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claimledger.label_blind import (
    assert_human_tree,
    assert_isolated_tree,
    build_bundle,
    committed_files_match,
    prepare_agent_view,
    write_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Regenerate the committed export")
    parser.add_argument("--check", action="store_true", help="Fail if the committed export drifted")
    parser.add_argument("--agent-dir", type=Path, help="Copy the model view outside the repository")
    args = parser.parse_args()
    if not any((args.write, args.check, args.agent_dir)):
        parser.error("Pass --write, --check, or --agent-dir.")
    bundle = build_bundle(ROOT / "benchmark" / "candidates")
    if args.write:
        write_bundle(ROOT, bundle)
    if args.agent_dir:
        prepare_agent_view(args.agent_dir, ROOT, bundle)
    if args.check or args.write:
        if not committed_files_match(ROOT, bundle):
            print("Label-blind export does not match the generator.", file=sys.stderr)
            return 2
        assert_isolated_tree(ROOT / "benchmark" / "evaluation" / "isolated")
        assert_human_tree(ROOT / "benchmark" / "evaluation" / "human_review")
    print(
        f"protocol={bundle['protocol']['protocol_version']} "
        f"rows={bundle['protocol']['isolated_rows']} "
        f"rejected_shuffles={bundle['rejected_shuffles']} "
        f"calibration={bundle['protocol']['calibration_rows']} "
        f"external_test={bundle['protocol']['creates_external_blind_test']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
