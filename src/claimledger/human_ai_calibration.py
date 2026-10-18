"""Document conversational Human–AI calibration labels.

Statistics are computed from the stored responses and the committed AI files.
This module does not write the canonical review queue, invent a reviewer
identity, or treat agreement as accuracy.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .calibration import (
    adjudication_digest,
    apply_plan,
    cohen_kappa,
    plan_queue_import,
    validate_sheets,
)
from .label_blind import CLASSES, permitted_passage
from .review import locate_unique_quote

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
    reviewed_queue_rows = [
        row for row in queue
        if row["human_reviewed"] == "True" or row["reviewed_label"] != ""
    ]
    if any(row["human_reviewed"] != "True" or row["reviewed_label"] == "" for row in reviewed_queue_rows):
        raise CalibrationStudyError("A queue row mixes a review label with an unreviewed flag.")
    if any(row["expected"] == "" for row in queue):
        raise CalibrationStudyError("An author label is missing.")
    second_doc = json.loads((study_dir / "second_reviewer_responses.json").read_text(encoding="utf-8"))
    second_labels = _labels_from_codes(second_doc["original_codes_in_packet_order"])
    if len(second_labels) != len(joined):
        raise CalibrationStudyError("The second reviewer response list is not 30 rows.")
    for row, label in zip(joined, second_labels, strict=True):
        row["second_reviewer_label"] = label
    second_vs_original = _agreement_block(
        second_labels,
        [row["original_human_label"] for row in joined],
        "second_reviewer_vs_original_human",
    )
    second_vs_revised = _agreement_block(
        second_labels,
        revised_labels,
        "second_reviewer_vs_revised_human",
    )
    second_vs_ai = _agreement_block(
        second_labels,
        [row["ai_second_opinion"] for row in joined],
        "second_reviewer_vs_ai",
    )
    second_differences = [
        {
            "position": row["position"],
            "packet_id": row["packet_id"],
            "canonical_id": row["canonical_id"],
            "claim": row["claim"],
            "original_human_label": row["original_human_label"],
            "second_reviewer_label": row["second_reviewer_label"],
            "ai_second_opinion": row["ai_second_opinion"],
        }
        for row in joined
        if row["second_reviewer_label"] != row["original_human_label"]
    ]
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
        "second_reviewer": {
            "response_origin": second_doc["response_origin"],
            "user_described_as_independent_reviewer": True,
            "reviewer_identity_verified": False,
            "response_timestamp": None,
            "formal_review_sheet": False,
            "formal_queue_import_recorded": sum(row["human_reviewed"] == "True" for row in queue) == 30,
            "differences_from_original_human": second_differences,
            "versus_original_human": second_vs_original,
            "versus_revised_human": second_vs_revised,
            "versus_ai": second_vs_ai,
        },
        "integrity": {
            "review_queue_sha256": _sha256(queue_path),
            "human_reviewed_rows_in_queue": sum(row["human_reviewed"] == "True" for row in queue),
            "reviewed_labels_empty": True,
            "author_expected_preserved": True,
            "question_13_author_expected": author_label,
            "reviewer_b_decisions": reviewer_b_decisions,
            "gold_set_rows": benchmark["gold_set_rows"],
            "gold_benchmark_released": benchmark["gold_benchmark_released"],
            "calibration_import_applied": benchmark["calibration_import_applied"],
            "formal_import_approval_generated": False,
        },
    }


def render_report_json(study: dict) -> str:
    return json.dumps(study, indent=2, ensure_ascii=False) + "\n"


def _matrix_table(matrix: dict[str, dict[str, int]], row_name: str = "Human",
                  column_name: str = "AI") -> list[str]:
    header = f"| {row_name} \\ {column_name} | " + " | ".join(CLASSES) + " |"
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
        "## Second reviewer",
        "",
        "A later set of 30 labels was supplied as another reviewer's answers. The user "
        "described that person as independent. The formal sheets name Steven and David. "
        "Those names, and the adjudicator account id, do not prove a real-world identity. "
        "The completed sheets and the queue import are in `benchmark/evaluation/formal_review/`. "
        "The label-blind template for reviewer B stays empty. The import does not release gold. "
        "The original "
        f"{original['agreements']}/{original['n']} comparison is unchanged.",
        "",
    ])
    second = study["second_reviewer"]
    versus_original = second["versus_original_human"]
    versus_ai = second["versus_ai"]
    versus_revised = second["versus_revised_human"]
    lines.extend([
        f"- Agreements with the original human labels: "
        f"{versus_original['agreements']}/{versus_original['n']}.",
        f"- Cohen's kappa against the original human labels: {versus_original['cohen_kappa']:.2f}.",
        f"- Agreements with the AI second opinions: "
        f"{versus_ai['agreements']}/{versus_ai['n']}.",
        f"- Agreements with the first person's revised labels: "
        f"{versus_revised['agreements']}/{versus_revised['n']}.",
        "",
        "Positions that differ from the original human label:",
        "",
    ])
    if not second["differences_from_original_human"]:
        lines.append("None.")
    for row in second["differences_from_original_human"]:
        lines.append(
            f"- {row['position']}. `{row['packet_id']}` / `{row['canonical_id']}`: "
            f"original human `{row['original_human_label']}`, "
            f"second reviewer `{row['second_reviewer_label']}`, "
            f"AI `{row['ai_second_opinion']}`."
        )
    lines.extend([
        "",
        "Confusion matrix, second reviewer by row and original human label by column:",
        "",
        *_matrix_table(
            versus_original["confusion_matrix_human_rows_ai_columns"],
            "Second reviewer",
            "Original human",
        ),
        "",
        "These comparisons are `human_ai_agreement` or conversational label agreement. "
        "They are not accuracy.",
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
        "- Reviewer B's formal sheet is still empty. The additional 30 labels are a "
        "conversational record. Identity, independence, and evidence spans were not verified.",
        "",
        "## Next steps",
        "",
        "Keep this session out of the gold queue. The additional conversational labels still "
        "need a timestamped sheet and evidence spans before they can enter the review queue. "
        "Do not import these conversational labels through the calibration approval gate.",
        "",
    ])
    return "\n".join(lines)


def _csv_text(rows: list[dict], fieldnames: list[str]) -> str:
    import io
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _evidence_span(passage: str, label: str, quote: str, position: int) -> tuple[str, str, str]:
    if label == "insufficient":
        return "", "", ""
    if not quote or passage.find(quote) < 0 or passage.find(quote, passage.find(quote) + 1) != -1:
        raise CalibrationStudyError(f"Position {position} has no unique evidence quote.")
    start = passage.find(quote)
    return str(start), str(start + len(quote)), quote


def assemble_formal_review(root: Path) -> dict:
    """Build the two formal sheets and the queue update. This does not write files."""
    study_dir = root / "benchmark" / "evaluation" / "human_ai_calibration"
    candidates = root / "benchmark" / "candidates"
    evaluation = root / "benchmark" / "evaluation"
    original = json.loads((study_dir / "human_original_responses.json").read_text(encoding="utf-8"))
    second = json.loads((study_dir / "second_reviewer_responses.json").read_text(encoding="utf-8"))
    evidence = json.loads((study_dir / "reviewer_evidence.json").read_text(encoding="utf-8"))
    author_quotes = json.loads((study_dir / "author_evidence_quotes.json").read_text(encoding="utf-8"))
    packet = _read_jsonl(evaluation / "human_review" / "calibration_packet.jsonl")
    mapping = json.loads((evaluation / "audit" / "calibration_mapping.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidates / "manifest.json").read_text(encoding="utf-8"))
    by_packet = {row["packet_id"]: row for row in mapping["cases"]}
    by_hash = {digest: name for name, digest in manifest["document_sha256"].items()}
    steven_labels = _labels_from_codes(original["original_codes_in_packet_order"])
    david_labels = _labels_from_codes(second["original_codes_in_packet_order"])
    quotes = {int(key): value for key, value in evidence["quotes_by_position"].items()}
    overrides = {int(key): value for key, value in evidence["adjudication_overrides_by_position"].items()}
    if not (len(packet) == len(steven_labels) == len(david_labels) == 30):
        raise CalibrationStudyError("Formal review inputs are not 30 rows.")
    sheet_fields = [
        "packet_id", "reviewer_slot", "reviewer_id", "reviewed_at", "reviewed_label",
        "evidence_start", "evidence_end", "evidence_quote", "notes",
    ]
    steven_rows = []
    david_rows = []
    adjudications = []
    documents = {
        name: (candidates / "documents" / name).read_bytes()
        for name in manifest["document_sha256"]
    }
    with (candidates / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        queue_rows = list(csv.DictReader(handle))
    for position, row in enumerate(packet, start=1):
        packet_id = row["packet_id"]
        if packet_id != original["packet_ids_in_order"][position - 1]:
            raise CalibrationStudyError("Formal review packet order does not match the frozen ids.")
        passage = row["passage"]
        steven_label = steven_labels[position - 1]
        david_label = david_labels[position - 1]
        quote = quotes.get(position, "")
        steven_start, steven_end, steven_quote = _evidence_span(passage, steven_label, quote, position)
        david_start, david_end, david_quote = _evidence_span(passage, david_label, quote, position)
        if steven_label == david_label:
            adjudicated = steven_label
            if position in overrides and overrides[position] != adjudicated:
                raise CalibrationStudyError(f"Position {position} already agrees.")
        else:
            adjudicated = overrides.get(position)
            if adjudicated not in CLASSES:
                raise CalibrationStudyError(f"Position {position} needs an adjudication label.")
        if adjudicated == "insufficient" and not quote:
            adj_start, adj_end, adj_quote = "", "", ""
        else:
            if not quote or passage.find(quote) < 0:
                raise CalibrationStudyError(f"Position {position} is missing a source quote.")
            adj_start_i = passage.find(quote)
            adj_start, adj_end, adj_quote = str(adj_start_i), str(adj_start_i + len(quote)), quote
        mapped = by_packet[packet_id]
        filename = by_hash[mapped["document_sha256"]]
        full_text = (candidates / "documents" / filename).read_text(encoding="utf-8")
        if adj_quote:
            locate_unique_quote(full_text, adj_quote)
        if steven_quote:
            locate_unique_quote(full_text, steven_quote)
        if david_quote:
            locate_unique_quote(full_text, david_quote)
        author_quote = author_quotes[str(position)]
        notes = ""
        if author_quote and author_quote != adj_quote:
            notes = f"author_evidence_quote={author_quote}"
        steven_rows.append({
            "packet_id": packet_id,
            "reviewer_slot": "A",
            "reviewer_id": original["reviewer_id"],
            "reviewed_at": original["reviewed_at"],
            "reviewed_label": steven_label,
            "evidence_start": steven_start,
            "evidence_end": steven_end,
            "evidence_quote": steven_quote,
            "notes": "",
        })
        david_rows.append({
            "packet_id": packet_id,
            "reviewer_slot": "B",
            "reviewer_id": second["reviewer_id"],
            "reviewed_at": second["reviewed_at"],
            "reviewed_label": david_label,
            "evidence_start": david_start,
            "evidence_end": david_end,
            "evidence_quote": david_quote,
            "notes": "",
        })
        adjudications.append({
            "packet_id": packet_id,
            "canonical_id": mapped["canonical_id"],
            "claim": row["claim"],
            "dataset_version": manifest["dataset_version"],
            "document_sha256": mapped["document_sha256"],
            "passage_sha256": hashlib.sha256(passage.encode("utf-8")).hexdigest(),
            "adjudicated_label": adjudicated,
            "evidence_quote": adj_quote,
            "evidence_start": adj_start,
            "evidence_end": adj_end,
            "adjudicator": evidence["adjudicator_id"],
            "adjudicated_at": evidence["adjudicated_at"],
            "reviewer_a_id": original["reviewer_id"],
            "reviewer_b_id": second["reviewer_id"],
            "reviewer_a_label": steven_label,
            "reviewer_b_label": david_label,
            "reviewer_a_reviewed_at": original["reviewed_at"],
            "reviewer_b_reviewed_at": second["reviewed_at"],
            "review_notes": notes,
        })
    validated = validate_sheets(
        packet, steven_rows, david_rows, mapping["cases"], manifest["document_sha256"], documents,
    )
    approval = {
        "decision": "approved_for_queue_import",
        "approver": evidence["adjudicator_id"],
        "approved_at": evidence["write_approved_at"],
        "approval_id": f"{evidence['adjudicator_id']}-{evidence['write_approved_at']}",
        "dataset_version": manifest["dataset_version"],
        "adjudication_sha256": adjudication_digest(adjudications),
        "independence_attested": evidence["independence_attested_by_user"],
        "independence_verified": False,
    }
    plan = plan_queue_import(
        adjudications,
        approval,
        validated_pairs=validated["validated_pairs"],
        queue_rows=queue_rows,
        dataset_version=manifest["dataset_version"],
        documents=documents,
        manifest_hashes=manifest["document_sha256"],
    )
    write_action = {
        "decision": "approved_queue_write",
        "approver": evidence["adjudicator_id"],
        "approved_at": evidence["write_approved_at"],
        "dataset_version": manifest["dataset_version"],
        "adjudication_sha256": plan["adjudication_sha256"],
    }
    updated = apply_plan(queue_rows, plan, write_action=write_action)
    fieldnames = list(queue_rows[0].keys())
    return {
        "queue_csv": _csv_text(updated, fieldnames),
        "sheet_steven": _csv_text(steven_rows, sheet_fields),
        "sheet_david": _csv_text(david_rows, sheet_fields),
        "adjudications_json": json.dumps(adjudications, indent=2, ensure_ascii=False) + "\n",
        "approval_json": json.dumps(
            {"approval": approval, "write_action": write_action, "plan_gold_benchmark_released": plan["gold_benchmark_released"]},
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        "paired_cases": validated["paired_cases"],
        "sheet_disagreements": validated["disagreements"],
        "gold_benchmark_released": plan["gold_benchmark_released"],
        "independence_verified": plan["independence_verified"],
    }


def render_second_reviewer_csv(root: Path) -> str:
    study_dir = root / "benchmark" / "evaluation" / "human_ai_calibration"
    original = json.loads((study_dir / "human_original_responses.json").read_text(encoding="utf-8"))
    second = json.loads((study_dir / "second_reviewer_responses.json").read_text(encoding="utf-8"))
    labels = _labels_from_codes(second["original_codes_in_packet_order"])
    lines = ["position,packet_id,second_reviewer_label"]
    for position, (packet_id, label) in enumerate(
        zip(original["packet_ids_in_order"], labels, strict=True), start=1,
    ):
        lines.append(f"{position},{packet_id},{label}")
    return "\n".join(lines) + "\n"


def render_original_csv(root: Path) -> str:
    study_dir = root / "benchmark" / "evaluation" / "human_ai_calibration"
    original = json.loads((study_dir / "human_original_responses.json").read_text(encoding="utf-8"))
    labels = _labels_from_codes(original["original_codes_in_packet_order"])
    lines = ["position,packet_id,original_human_label"]
    for position, (packet_id, label) in enumerate(zip(original["packet_ids_in_order"], labels, strict=True), start=1):
        lines.append(f"{position},{packet_id},{label}")
    return "\n".join(lines) + "\n"
