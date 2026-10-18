"""Document one conversational Human–AI calibration session.

Statistics are computed from the stored responses and the committed AI files.
This module does not write the canonical review queue, invent a second human
reviewer, or treat agreement as accuracy.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .calibration import cohen_kappa
from .label_blind import CLASSES, permitted_passage

STUDY_SCHEMA = "claimledger.human_ai_calibration_report.v1"
CODE_MAP = {"S": "supported", "C": "contradicted", "I": "insufficient"}
AI_FILES = (
    "semantic_review_18.json",
    "semantic_review_remaining_90.json",
)


class CalibrationStudyError(ValueError):
    """Raised when the stored session does not match the current packet."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _labels_from_codes(codes: str) -> list[str]:
    try:
        return [CODE_MAP[character] for character in codes]
    except KeyError as exc:
        raise CalibrationStudyError(f"Unknown label code: {exc}") from exc


def _load_ai(directory: Path) -> tuple[dict[str, str], list[dict]]:
    verdicts: dict[str, str] = {}
    sources = []
    for name in AI_FILES:
        path = directory / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources.append({
            "file": f"benchmark/candidates/ai_second_opinion/{name}",
            "sha256": _sha256(path),
            "recorded_commit": payload.get("commit") or payload.get("source_ref"),
            "review_type": payload.get("review_type"),
            "paid_api_calls": payload.get("paid_api_calls"),
            "dataset_version": payload.get("dataset_version"),
            "n": payload.get("n"),
            "rigorous_independent_blind_protocol": False,
        })
        for result in payload["results"]:
            case_id = result["case_id"]
            if case_id in verdicts:
                raise CalibrationStudyError(f"Duplicate AI annotation: {case_id}")
            verdicts[case_id] = result["ai_verdict"]
    return verdicts, sources


def _confusion(human_labels: list[str], ai_labels: list[str]) -> dict[str, dict[str, int]]:
    matrix = {human: {ai: 0 for ai in CLASSES} for human in CLASSES}
    for human, ai in zip(human_labels, ai_labels, strict=True):
        matrix[human][ai] += 1
    return matrix


def _agreement_block(human_labels: list[str], ai_labels: list[str], metric: str) -> dict:
    agreements = sum(human == ai for human, ai in zip(human_labels, ai_labels, strict=True))
    count = len(human_labels)
    per_class = {
        label: sum(human == ai == label for human, ai in zip(human_labels, ai_labels, strict=True))
        for label in CLASSES
    }
    return {
        "metric": metric,
        "n": count,
        "agreements": agreements,
        "disagreements": count - agreements,
        "observed_agreement": agreements / count,
        "cohen_kappa": cohen_kappa(human_labels, ai_labels),
        "confusion_matrix_human_rows_ai_columns": _confusion(human_labels, ai_labels),
        "per_class_agreement_counts": per_class,
        "is_accuracy": False,
        "is_independent_inter_annotator_agreement": False,
        "is_evidence_of_ai_correctness": False,
    }


def _sheet_decision_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for row in csv.DictReader(handle) if (row.get("reviewed_label") or "").strip())


def build_study(root: Path) -> dict:
    """Join the stored conversational answers to the committed AI notes."""
    study_dir = root / "benchmark" / "evaluation" / "human_ai_calibration"
    evaluation = root / "benchmark" / "evaluation"
    candidates = root / "benchmark" / "candidates"
    original = json.loads((study_dir / "human_original_responses.json").read_text(encoding="utf-8"))
    revision = json.loads((study_dir / "revision.json").read_text(encoding="utf-8"))
    packet = _read_jsonl(evaluation / "human_review" / "calibration_packet.jsonl")
    mapping_path = evaluation / "audit" / "calibration_mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    by_packet = {row["packet_id"]: row for row in mapping["cases"]}
    codes = original["original_codes_in_packet_order"]
    labels = _labels_from_codes(codes)
    frozen_ids = original["packet_ids_in_order"]
    if not (len(packet) == len(labels) == len(frozen_ids) == len(set(frozen_ids))):
        raise CalibrationStudyError("The original response list is not 30 unique packet rows.")
    ai_verdicts, ai_sources = _load_ai(candidates / "ai_second_opinion")
    joined = []
    for position, (row, label, frozen_id) in enumerate(zip(packet, labels, frozen_ids, strict=True), start=1):
        if row["packet_id"] != frozen_id:
            raise CalibrationStudyError(
                "Packet order no longer matches the frozen Human–AI calibration packet ids."
            )
        mapped = by_packet.get(frozen_id)
        if mapped is None:
            raise CalibrationStudyError(f"Packet id is missing from the audit mapping: {frozen_id}")
        canonical_id = mapped["canonical_id"]
        if canonical_id not in ai_verdicts:
            raise CalibrationStudyError(f"No committed AI second opinion for {canonical_id}")
        if row["claim"] != mapped.get("claim", row["claim"]) and "claim" in mapped:
            raise CalibrationStudyError("Mapping claim does not match the packet.")
        joined.append({
            "position": position,
            "packet_id": frozen_id,
            "canonical_id": canonical_id,
            "claim": row["claim"],
            "original_human_label": label,
            "ai_second_opinion": ai_verdicts[canonical_id],
        })
    if revision["position"] != 13 or revision["packet_id"] != joined[12]["packet_id"]:
        raise CalibrationStudyError("The recorded revision is not question 13.")
    target = joined[12]
    if target["original_human_label"] != revision["original_human_label"]:
        raise CalibrationStudyError("The revision does not match the stored original human label.")
    if target["ai_second_opinion"] != revision["ai_second_opinion"]:
        raise CalibrationStudyError("The revision does not match the committed AI second opinion.")
    if revision["event"] != "human_error_corrected_after_ai_feedback":
        raise CalibrationStudyError("The revision event type is not the recorded correction.")
    revised_labels = [row["original_human_label"] for row in joined]
    revised_labels[12] = revision["revised_human_label"]
    if revised_labels[12] == target["original_human_label"]:
        raise CalibrationStudyError("The revision did not change the question 13 label.")
    original_block = _agreement_block(
        [row["original_human_label"] for row in joined],
        [row["ai_second_opinion"] for row in joined],
        "human_ai_agreement",
    )
    revised_block = _agreement_block(
        revised_labels,
        [row["ai_second_opinion"] for row in joined],
        "human_ai_agreement_after_feedback",
    )
    disagreements = [
        row for row in joined
        if row["original_human_label"] != row["ai_second_opinion"]
    ]
    queue_path = candidates / "review_queue.csv"
    with queue_path.open(encoding="utf-8", newline="") as handle:
        queue = list(csv.DictReader(handle))
    queue_by_id = {row["id"]: row for row in queue}
    author_label = queue_by_id[target["canonical_id"]]["expected"]
    status = json.loads((root / "funding" / "status.json").read_text(encoding="utf-8"))
    benchmark = status["benchmark"]
    reviewer_b_decisions = _sheet_decision_count(
        evaluation / "human_review" / "response_sheet_B.csv"
    )
    if reviewer_b_decisions != 0:
        raise CalibrationStudyError("Reviewer B's sheet is no longer empty.")
    if any(row["human_reviewed"] != "False" or row["reviewed_label"] != "" for row in queue):
        raise CalibrationStudyError("The canonical queue has a human-reviewed row.")
    manifest = json.loads((candidates / "manifest.json").read_text(encoding="utf-8"))
    by_hash = {digest: name for name, digest in manifest["document_sha256"].items()}
    source_name = by_hash[by_packet[target["packet_id"]]["document_sha256"]]
    source_text = permitted_passage(
        (candidates / "documents" / source_name).read_text(encoding="utf-8")
    ).strip()
    return {
        "schema": STUDY_SCHEMA,
        "study_type": "human_ai_calibration",
        "not_two_human_independent_review": True,
        "not_gold_benchmark": True,
        "not_controlled_blind_model_evaluation": True,
        "response_origin": original["response_origin"],
        "response_timestamp": None,
        "reviewer_identity_verified": False,
        "independently_verified_human_review": False,
        "independent_external_review": False,
        "encrypted_ai_answer_artifact_used": False,
        "dataset_version": manifest["dataset_version"],
        "mapping": {
            "file": "benchmark/evaluation/audit/calibration_mapping.json",
            "sha256": _sha256(mapping_path),
            "protocol_version": mapping["protocol_version"],
            "human_packet_seed": mapping["human_packet_seed"],
        },
        "ai_sources": ai_sources,
        "ai_generation_limitation": (
            "The committed AI annotations predate this comparison. "
            "They were not produced under a rigorously independent blind protocol."
        ),
        "cases": joined,
        "original": original_block,
        "disagreements": disagreements,
        "revision": {
            **revision,
            "canonical_id": target["canonical_id"],
            "claim": target["claim"],
            "author_label_in_canonical_queue": author_label,
            "source_excerpt": source_text,
            "author_label_changed": False,
            "independent_adjudicator": False,
            "original_response_overwritten": False,
        },
        "after_feedback": {
            **revised_block,
            "consensus_after_feedback": True,
            "replaces_original_result": False,
        },
        "integrity": {
            "review_queue_sha256": _sha256(queue_path),
            "human_reviewed_rows_in_queue": 0,
            "reviewed_labels_empty": True,
            "author_expected_preserved": True,
            "question_13_author_expected": author_label,
            "reviewer_b_decisions": 0,
            "gold_set_rows": benchmark["gold_set_rows"],
            "gold_benchmark_released": benchmark["gold_benchmark_released"],
            "calibration_import_applied": benchmark["calibration_import_applied"],
            "formal_import_approval_generated": False,
        },
    }


def render_report_json(study: dict) -> str:
    return json.dumps(study, indent=2, ensure_ascii=False) + "\n"


def _matrix_table(matrix: dict[str, dict[str, int]]) -> list[str]:
    header = "| Human \\ AI | " + " | ".join(CLASSES) + " |"
    rule = "| --- | " + " | ".join("---" for _ in CLASSES) + " |"
    lines = [header, rule]
    for human in CLASSES:
        cells = " | ".join(str(matrix[human][ai]) for ai in CLASSES)
        lines.append(f"| {human} | {cells} |")
    return lines


def render_report_markdown(study: dict) -> str:
    original = study["original"]
    revised = study["after_feedback"]
    disagreement = study["disagreements"][0]
    revision = study["revision"]
    kappa = original["cohen_kappa"]
    lines = [
        "# Human–AI calibration session, 30 cases",
        "",
        "This is a Human–AI calibration study. It is not a two-human independent review, "
        "not a gold benchmark, and not a controlled blind model evaluation.",
        "",
        "## Objective and method",
        "",
        "One person recorded a label for each row of `calibration_packet.jsonl` before seeing "
        "a comparison with the committed AI second opinions. The join uses that file's order "
        "and `packet_id`. It does not use the canonical case-id suffix. The AI labels are read "
        "from the two committed annotation files. They were not rerun for this report.",
        "",
        "The response origin is a user-provided conversational judgment. The exact original "
        "response timestamp and a verified real-world identity are not available, so neither "
        "is recorded. The answers are not marked as independently verified human reviews. "
        "If the project maintainer is also the dataset author, this person is not an "
        "independent external reviewer.",
        "",
        "## Dataset",
        "",
        f"- Dataset version: `{study['dataset_version']}`.",
        f"- Mapping: `{study['mapping']['file']}` "
        f"(`{study['mapping']['protocol_version']}`, seed {study['mapping']['human_packet_seed']}, "
        f"SHA-256 `{study['mapping']['sha256']}`).",
        "- AI sources, with the commit recorded inside each file:",
    ]
    for source in study["ai_sources"]:
        lines.append(
            f"  - `{source['file']}` commit `{source['recorded_commit']}`, "
            f"SHA-256 `{source['sha256']}`, paid API calls {source['paid_api_calls']}."
        )
    lines.extend([
        "",
        study["ai_generation_limitation"] + " No encrypted AI-answer artifact was used.",
        "",
        "## Original human responses",
        "",
        "The 30 original labels, in packet order, are stored in `human_original_responses.json`. "
        "That file is the immutable record. The table below is derived from it.",
        "",
        "| # | Packet id | Canonical id | Original human label | AI second opinion |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in study["cases"]:
        lines.append(
            f"| {row['position']} | `{row['packet_id']}` | `{row['canonical_id']}` | "
            f"{row['original_human_label']} | {row['ai_second_opinion']} |"
        )
    lines.extend([
        "",
        "## Original agreement",
        "",
        "Metric name: `human_ai_agreement`. This is not accuracy and not independent "
        "human inter-annotator agreement.",
        "",
        f"- Cases: {original['n']}.",
        f"- Agreements: {original['agreements']}.",
        f"- Disagreements: {original['disagreements']}.",
        f"- Observed agreement: {original['agreements']}/{original['n']}.",
        f"- Cohen's kappa: {kappa:.2f}.",
        "",
        "Confusion matrix, human labels by row and AI labels by column:",
        "",
        *_matrix_table(original["confusion_matrix_human_rows_ai_columns"]),
        "",
        "Per-class agreement counts (both sides chose that label): "
        + ", ".join(
            f"{label} {original['per_class_agreement_counts'][label]}"
            for label in CLASSES
        )
        + ".",
        "",
        "## Question 13",
        "",
        f"Position {disagreement['position']}, packet `{disagreement['packet_id']}`, "
        f"canonical `{disagreement['canonical_id']}`.",
        "",
        f"Claim: {disagreement['claim']}",
        "",
        f"Source passage: {revision['source_excerpt']}",
        "",
        f"Original human label: `{revision['original_human_label']}`.",
        f"Committed AI second opinion: `{revision['ai_second_opinion']}`.",
        f"Canonical author `expected` at the time of this report: "
        f"`{revision['author_label_in_canonical_queue']}`. That author label was not changed.",
        "",
        "The AI note in `semantic_review_18.json` says that not mentioning nuts is not an "
        "explicit exclusion. The original human judgment treated the omission as a contradiction.",
        "",
        "## Correction after feedback",
        "",
        "After the comparison, the same person acknowledged a reasoning error and revised "
        "question 13 from `contradicted` to `insufficient`. The stated reason is that the "
        "source says the recipe uses oats and honey and does not mention nuts, and that not "
        "mentioning nuts does not establish their absence.",
        "",
        "- Event: `human_error_corrected_after_ai_feedback`.",
        f"- `original_human_label`: `{revision['original_human_label']}`.",
        f"- `ai_second_opinion`: `{revision['ai_second_opinion']}`.",
        f"- `revised_human_label`: `{revision['revised_human_label']}`.",
        f"- `revision_trigger`: `{revision['revision_trigger']}`.",
        f"- `revision_reason`: `{revision['revision_reason']}`.",
        f"- `revision_confirmed_by_user`: {str(revision['revision_confirmed_by_user']).lower()}.",
        "",
        "The original response file is unchanged. There is no independent adjudicator. "
        "No evidence quote or timestamp was invented for a formal review sheet.",
        "",
        "## Agreement after feedback",
        "",
        "These figures are separate from the original result. They do not replace "
        f"{original['agreements']}/{original['n']}.",
        "",
        f"- Agreements: {revised['agreements']}/{revised['n']}.",
        f"- Remaining disagreements: {revised['disagreements']}.",
        f"- Cohen's kappa: {revised['cohen_kappa']:.2f}.",
        "",
        f"{revised['agreements']}/{revised['n']} is consensus after feedback. It is not "
        "independent accuracy, and it is not evidence that the AI judgments are all correct.",
        "",
        "## Threats to validity",
        "",
        "- The candidate set is synthetic and author-labeled.",
        "- The AI notes were not produced under a rigorously independent blind protocol. "
        "Earlier discussion had already exposed dataset information.",
        "- The person who labeled these 30 rows may overlap with the dataset author or "
        "project maintainer. Identity was not verified.",
        "- The revised label depends on seeing the AI comparison.",
        "- The 30 rows are a small, intentionally class-balanced calibration subset, not a "
        "random sample of a broader population.",
        "- Reviewer B's sheet is empty. There is no second human rater.",
        "",
        "## Next steps",
        "",
        "Keep this session out of the gold queue. A later study needs a second person who "
        "did not write the items, timestamped sheets with evidence spans, and the label-blind "
        "export so case-id suffixes are not visible. Do not import these conversational "
        "labels through the calibration approval gate.",
        "",
    ])
    return "\n".join(lines)


def render_original_csv(root: Path) -> str:
    study_dir = root / "benchmark" / "evaluation" / "human_ai_calibration"
    original = json.loads((study_dir / "human_original_responses.json").read_text(encoding="utf-8"))
    labels = _labels_from_codes(original["original_codes_in_packet_order"])
    lines = ["position,packet_id,original_human_label"]
    for position, (packet_id, label) in enumerate(zip(original["packet_ids_in_order"], labels, strict=True), start=1):
        lines.append(f"{position},{packet_id},{label}")
    return "\n".join(lines) + "\n"
