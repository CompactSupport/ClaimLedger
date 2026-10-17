#!/usr/bin/env python3
"""Evaluate the three candidate shards and pool every case pair.

Macro-F1 is computed once on all pairs. It is not the mean of the shard scores.
OpenAI runs only when ``--allow-paid`` is set.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from claimledger.candidates import aggregate, assert_shard_outputs_match_sources, load_split

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "benchmark" / "candidates"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("local", "openai"), default="local")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--allow-paid", action="store_true",
                        help="Explicitly enable optional OpenAI API spend")
    args = parser.parse_args()
    if args.backend != "local" and not args.allow_paid:
        print("Refusing network inference without --allow-paid", file=sys.stderr)
        return 2
    datasets = sorted(CANDIDATES.glob("shard-*.jsonl"))
    if len(datasets) != 3:
        print("Expected exactly 3 candidate shards", file=sys.stderr)
        return 2
    outdir = ROOT / "output" / "candidate_benchmark"
    outdir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict] = []
    rows: list[list[dict]] = []
    for path in datasets:
        result_path = outdir / f"{path.stem}-result.json"
        command = [
            sys.executable, "-m", "claimledger", "evaluate",
            "--dataset", str(path),
            "--backend", args.backend,
            "--model", args.model,
            "--out", str(result_path),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        outputs.append(json.loads(result_path.read_text(encoding="utf-8")))
        rows.append([
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ])
    manifest = json.loads((CANDIDATES / "manifest.json").read_text(encoding="utf-8"))
    with (CANDIDATES / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        queue_rows = list(csv.DictReader(handle))
    assert_shard_outputs_match_sources(
        outputs, rows, queue_rows, manifest["document_sha256"], CANDIDATES,
    )
    summary = aggregate(outputs, rows, load_split())
    summary["paid_inference"] = args.backend != "local"
    target = outdir / "combined-summary.json"
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
