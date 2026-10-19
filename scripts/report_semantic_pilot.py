#!/usr/bin/env python3
"""Write or check the first semantic-pilot report.

This command does not launch a model. A missing Codex CLI is a blocker, not a
mock score.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claimledger.semantic_pilot import (
    DATASET_GIT_COMMIT,
    SELECTION_SEED,
    inference_blocker,
    select_internal_subset,
    subset_attempt_note,
    subset_case_hash,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark" / "evaluation" / "semantic_pilot"
FROZEN_RUN = OUT / "codex_subscription_run.json"


def _load_cases() -> list[dict]:
    adjudications = json.loads(
        (ROOT / "benchmark" / "evaluation" / "formal_review" / "adjudications.json").read_text(encoding="utf-8")
    )
    mapping = {
        row["canonical_id"]: row
        for row in json.loads(
            (ROOT / "benchmark" / "evaluation" / "audit" / "id_mapping.json").read_text(encoding="utf-8")
        )["cases"]
    }
    cases = []
    for row in adjudications:
        joined = mapping[row["canonical_id"]]
        cases.append({
            "canonical_id": row["canonical_id"],
            "document": joined["document"],
            "evaluation_id": joined["evaluation_id"],
            "adjudicated_label": row["adjudicated_label"],
            "claim": row["claim"],
        })
    return cases


def build_report_files() -> dict[str, str]:
    chosen = select_internal_subset(_load_cases(), seed=SELECTION_SEED)
    evaluation_ids = [row["evaluation_id"] for row in chosen]
    case_hash = subset_case_hash(evaluation_ids)
    blocker = inference_blocker()
    frozen = json.loads(FROZEN_RUN.read_text(encoding="utf-8")) if FROZEN_RUN.is_file() else None
    if frozen is None:
        measured = [
            "## Measured predictions",
            "",
            "- Genuine predictions: 0.",
            "- Paid model calls: 0.",
            "- Accuracy, macro-F1, confusion matrix, quote validity, and latency are "
            "not reported because there are no genuine predictions.",
            "- `gold_benchmark_released` remains false.",
            "",
        ]
    else:
        metrics = frozen["metrics"]
        measured = [
            "## Subscription run",
            "",
            frozen["summary"],
            "",
            f"- CLI: `{frozen['cli_version']}` via the Microsoft Store package, not PATH.",
            f"- Login: `{frozen['login_status']}`.",
            f"- Model: `{frozen['model']}`. Reasoning effort: `{frozen['reasoning_effort']}`.",
            f"- Sandbox flag: `{frozen['sandbox_mode']}`. Config default was not used.",
            f"- Cases: {frozen['cases']}. Correct against adjudicated labels: {frozen['correct']}.",
            f"- Macro-F1: {metrics['macro_f1']}. Insufficient-prediction rate: {metrics['insufficient_prediction_rate']}.",
            f"- Quote validity: {frozen['quotes_valid']} of {frozen['cases']}.",
            "- `independent_external_test` is false. `independently_blinded` is false. "
            "`gold_benchmark_released` remains false.",
            "- Paid API-key calls: 0. The run used the ChatGPT subscription quota.",
            "",
            "## Measured predictions",
            "",
            f"- Genuine predictions: {frozen['genuine_predictions']}.",
            "- Paid model calls: 0.",
            "- The score is an internal comparison with the adjudicated labels. "
            "It is not an external-test accuracy.",
            "- `gold_benchmark_released` remains false.",
            "",
        ]
    manifest = json.loads(
        (ROOT / "benchmark" / "candidates" / "manifest.json").read_text(encoding="utf-8")
    )
    public = {
        "schema": "claimledger.semantic_pilot_subset.v1",
        "selection_seed": SELECTION_SEED,
        "case_set_sha256": case_hash,
        "dataset_version": manifest["dataset_version"],
        "dataset_git_commit": DATASET_GIT_COMMIT,
        "evaluation_ids": evaluation_ids,
        "independent_external_test": False,
    }
    audit = {
        "schema": "claimledger.semantic_pilot_subset_audit.v1",
        "selection_seed": SELECTION_SEED,
        "case_set_sha256": case_hash,
        "dataset_version": manifest["dataset_version"],
        "dataset_git_commit": DATASET_GIT_COMMIT,
        "comparison_label": "adjudicated_human_label",
        "independent_external_test": False,
        "label_derived_annotations_included": False,
        "cases": chosen,
    }
    if frozen is None:
        opening = (
            "This report does not contain a measured semantic-model score. "
            "No genuine model process was started, and mock output is not substituted."
        )
        blocker = inference_blocker() + "\n\n" + subset_attempt_note()
    else:
        opening = (
            "This report records one ChatGPT-subscription Codex run on the internal "
            "10-case subset. Mock output is not included in that score."
        )
        attempt = (
            "shutil.which does not find codex, gemini, or agy on PATH. "
            "The recorded run did not use that PATH lookup. It invoked the Microsoft Store "
            "Codex executable directly. That executable is not on PATH."
        )
        blocker = attempt
    report = "\n".join([
        "# Semantic pilot",
        "",
        opening,
        "",
        "## Label-derived annotations",
        "",
        "`semantic_review_remaining_90.json` is `label_derived_not_independent`. "
        "Every stored verdict matches the canonical case-id suffix. "
        "The historical results array was not regenerated. "
        "The 90/90 match and the combined 107/108 match are not independent AI accuracy.",
        "",
        "## Internal 10-case subset",
        "",
        f"- Selection seed: `{SELECTION_SEED}`.",
        f"- Case-set SHA-256: `{case_hash}`.",
        f"- Dataset version: `{manifest['dataset_version']}`.",
        f"- Dataset git commit: `{DATASET_GIT_COMMIT}`.",
        "- Opaque evaluation ids are in `subset_public.json`.",
        "- Adjudicated labels for an internal comparison are in `subset_audit.json`.",
        "- Cases that share a document stay together.",
        "- This subset is not an independent external test.",
        "",
        "## Inference blocker",
        "",
        blocker,
        "",
        "A verified subscription and one record outside the repository can start "
        "Codex, Gemini, or Antigravity. `real_model_execution` is true only for that "
        "model subprocess. An in-process mock, and any other subprocess, stays false. "
        "A directory outside the repository and a stripped environment are not an "
        "operating-system sandbox. Any later run that can read this repository, "
        "including `subset_audit.json`, is not independently blinded.",
        "",
        *measured,
    ])
    return {
        "subset_public.json": json.dumps(public, indent=2) + "\n",
        "subset_audit.json": json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        "REPORT.md": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.write:
        parser.error("Pass --check or --write.")
    files = build_report_files()
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    if args.check:
        for name, text in files.items():
            path = OUT / name
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                print(f"{name} does not match the semantic-pilot generator.", file=sys.stderr)
                return 2
    frozen = json.loads(FROZEN_RUN.read_text(encoding="utf-8")) if FROZEN_RUN.is_file() else None
    print(f"genuine_predictions={0 if frozen is None else frozen['genuine_predictions']}")
    print("paid_model_calls=0")
    print("gold_benchmark_released=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
