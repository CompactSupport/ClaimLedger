import json
import subprocess
import sys
from pathlib import Path

from claimledger.candidates import aggregate, load_split
from claimledger.cli import evaluate_dataset

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "benchmark" / "candidates"


def test_local_candidate_run_pools_sixty_cases():
    outputs = []
    rows = []
    for path in sorted(CANDIDATES.glob("shard-*.jsonl")):
        outputs.append(evaluate_dataset(path, "local", "gpt-5-mini"))
        rows.append([
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ])
    summary = aggregate(outputs, rows, load_split())
    assert summary["examples"] == 60
    assert summary["gold_benchmark"] is False
    assert summary["human_reviewed"] is False
    assert summary["label_origin"] == "synthetic_author_labeled"
    assert summary["correct"] == 22
    assert summary["metrics"]["macro_f1"] != summary["mean_of_shard_macro_f1"]
    assert summary["baselines"]["always_abstain"]["macro_f1"] == 1 / 6
    assert summary["citation_validity_rate"] == 1.0
    assert summary["citation_total_quotes"] == 2
    assert summary["total_tokens"] == 0
    assert summary["splits"]["dev"]["n"] == 42
    assert summary["splits"]["held_out"]["n"] == 18
    assert summary["local_macro_f1_bootstrap_95"]["low"] < summary["metrics"]["macro_f1"]
    assert summary["metrics"]["macro_f1"] < summary["local_macro_f1_bootstrap_95"]["high"]
    assert len(summary["failure_modes"]) == 38


def test_openai_candidate_run_requires_an_explicit_paid_flag():
    completed = subprocess.run(
        [sys.executable, "scripts/evaluate_candidate_shards.py", "--backend", "openai"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "allow-paid" in completed.stderr
