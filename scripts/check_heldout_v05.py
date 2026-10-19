#!/usr/bin/env python3
"""Check or write the v0.5 held-out snapshot. This command does not start a model.

The research ledger is not regenerated. ``--write`` rebinds it only while it
still has no submissions, adjudications, approvals, or model contacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claimledger.heldout import LEDGER_NAME, catalog_dir, empty_ledger, generated_files

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_KEYS = ("reviewer_submissions", "human_adjudications", "approvals", "model_contacts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.check == args.write:
        print("Pass exactly one of --check or --write.", file=sys.stderr)
        return 2
    base = catalog_dir(ROOT)
    files = generated_files(ROOT)
    if args.write:
        for name, text in files.items():
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        stale = base / "human" / "adjudication_sheet.csv"
        if stale.is_file():
            stale.unlink()
    mismatched = [name for name, text in files.items()
                  if not (base / name).is_file() or (base / name).read_text(encoding="utf-8") != text]
    if mismatched:
        print("held-out snapshot differs: " + ", ".join(mismatched), file=sys.stderr)
        return 1
    freeze = json.loads((base / "freeze.json").read_text(encoding="utf-8"))
    ledger_path = base / LEDGER_NAME
    if args.write and not ledger_path.is_file():
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(
            json.dumps(empty_ledger(freeze["freeze_sha256"]), indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if not ledger_path.is_file():
        print("research ledger is missing", file=sys.stderr)
        return 1
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    populated = any(ledger.get(key) for key in RESEARCH_KEYS)
    if args.write and not populated and ledger.get("freeze_sha256") != freeze["freeze_sha256"]:
        ledger["freeze_sha256"] = freeze["freeze_sha256"]
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8", newline="\n")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("freeze_sha256") != freeze["freeze_sha256"]:
        print("research ledger is not bound to the freeze hash", file=sys.stderr)
        return 1
    contacts = ledger.get("model_contacts") or []
    print("heldout_v05_documents=8")
    print("heldout_v05_claims=16")
    print(f"model_contact_count={len(contacts)}")
    print("gold_benchmark_released=false")
    print("model_contact_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
