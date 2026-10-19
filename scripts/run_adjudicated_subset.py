#!/usr/bin/env python3
"""Check or run the frozen 10-case subset.

``--check`` loads the public records only. It does not open the adjudication
file and it does not start a model. ``--run`` starts a model only after
subscription billing is verified. API-key billing is not a fallback.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from claimledger.semantic_pilot import (
    SUBSCRIPTION_COMMANDS,
    PilotRefused,
    assert_codex_subscription,
    inference_blocker,
    launch_subscription_model,
    observe_subscription_billing,
    prepare_invocation,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmark" / "evaluation" / "semantic_pilot" / "subset_public.json"
ISOLATED = ROOT / "benchmark" / "evaluation" / "isolated" / "inputs.jsonl"
AUDIT = ROOT / "benchmark" / "evaluation" / "semantic_pilot" / "subset_audit.json"
PROVIDER_ORDER = ("antigravity", "gemini", "codex")


def load_public_records() -> list[dict]:
    """Load the frozen ids from the isolated inputs. Do not open the audit file."""
    public = json.loads(PUBLIC.read_text(encoding="utf-8"))
    rows = {}
    for line in ISOLATED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["evaluation_id"]] = row
    selected = []
    allowed = {"evaluation_id", "claim", "passage_id", "passage"}
    for evaluation_id in public["evaluation_ids"]:
        row = rows.get(evaluation_id)
        if row is None or set(row) != allowed:
            raise PilotRefused(f"The public subset id {evaluation_id} has no isolated record.")
        selected.append(row)
    if len(selected) != 10:
        raise PilotRefused("The public subset is not the frozen 10-case set.")
    return selected


def _settings_for(provider: str) -> dict | None:
    home = Path.home()
    if provider == "antigravity":
        path = home / ".gemini" / "antigravity-cli" / "settings.json"
    elif provider == "gemini":
        path = home / ".gemini" / "settings.json"
    else:
        return None
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Load the public 10 records. Do not start a model.")
    parser.add_argument("--run", action="store_true", help="Run the 10 records after subscription billing is verified.")
    args = parser.parse_args(argv)
    if args.check == args.run:
        print("Pass exactly one of --check or --run.", file=sys.stderr)
        return 2
    try:
        records = load_public_records()
    except (OSError, json.JSONDecodeError, PilotRefused) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.check:
        print("subset_records=10")
        print("adjudication_file_opened=false")
        print("processes_started=0")
        print("genuine_predictions=0")
        print(f"audit_path_present={str(AUDIT.is_file()).lower()}")
        return 0
    try:
        available = [name for name in PROVIDER_ORDER if shutil.which(SUBSCRIPTION_COMMANDS[name])]
        if not available:
            print(inference_blocker(), file=sys.stderr)
            print("processes_started=0")
            print("genuine_predictions=0")
            return 2
        provider = available[0]
        billing = observe_subscription_billing(provider, settings=_settings_for(provider))
        assert_codex_subscription(billing)
    except (OSError, json.JSONDecodeError, PilotRefused) as exc:
        print(str(exc), file=sys.stderr)
        print("processes_started=0")
        print("genuine_predictions=0")
        return 2
    results = []
    workspace = Path(tempfile.mkdtemp(prefix="claimledger-subset-"))
    try:
        for index, record in enumerate(records):
            invocation = prepare_invocation([record], workspace / f"case-{index}", ROOT)
            result = launch_subscription_model(
                provider,
                billing,
                allow_real_inference=True,
                invocation=invocation,
                repo_root=ROOT,
            )
            if result is None:
                raise PilotRefused("The model process did not return a recorded result.")
            results.append(result)
    except PilotRefused as exc:
        print(str(exc), file=sys.stderr)
        print(f"processes_started={sum(row.get('real_model_execution') is True for row in results)}")
        print("genuine_predictions=0")
        return 2
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    valid = [row for row in results if row.get("status") == "completed_valid" and row.get("real_model_execution") is True]
    print(f"processes_started={len(results)}")
    print(f"genuine_predictions={len(valid)}")
    print("adjudication_file_opened=false")
    print("scored=false")
    return 0 if len(valid) == len(records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
