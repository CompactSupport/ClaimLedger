#!/usr/bin/env python3
"""Check or write the v0.5 held-out freeze. This command does not start a model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claimledger.heldout import catalog_dir, generated_files

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.check == args.write:
        print("Pass exactly one of --check or --write.", file=sys.stderr)
        return 2
    files = generated_files(ROOT)
    base = catalog_dir(ROOT)
    if args.write:
        for name, text in files.items():
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    mismatched = []
    for name, text in files.items():
        path = base / name
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            mismatched.append(name)
    if mismatched:
        print("held-out files differ: " + ", ".join(mismatched), file=sys.stderr)
        return 1
    print("heldout_v05_documents=8")
    print("heldout_v05_claims=16")
    print("human_adjudication_complete=false")
    print("model_contact_count=0")
    print("model_contact_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
