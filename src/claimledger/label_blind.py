"""Deterministic label-blind views of the candidate set.

The canonical queue keeps its case IDs and author labels. Model-visible files
do not. This export is an internal control, not an independent external test.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from pathlib import Path

PROTOCOL_VERSION = "claimledger.evaluation_export.v1"
PROMPT_VERSION = "claimledger.inference_prompt.v1"
SEED = 20261017
HUMAN_PACKET_SEED = SEED + 1
EVALUATION_ID_SEED = SEED + 2
CALIBRATION_PER_CLASS = 10
CLASSES = ("supported", "contradicted", "insufficient")
MAX_SHUFFLE_DRAWS = 100_000

CANONICAL_ID_RE = re.compile(r"cl-\d{3}-\d")
DOCUMENT_NAME_RE = re.compile(r"d\d{3}\.md")
SCENARIO_HEADING_RE = re.compile(r"# Fictional scenario \d{3} \u2014 .+")
LABEL_WORD_RE = re.compile(r"\b(supported|contradicted|insufficient)\b")

FORBIDDEN_RECORD_KEYS = {
    "expected",
    "author_label",
    "ai_verdict",
    "reviewed_label",
    "human_reviewed",
    "reviewer",
    "reviewed_at",
    "review_notes",
    "evidence_quote",
    "canonical_id",
    "agrees_with_author",
    "label_origin",
    "document",
}

FLAG_CATEGORIES = {
    "cl-002-1": "paraphrase",
    "cl-006-1": "comparison",
    "cl-006-2": "comparison",
    "cl-006-3": "related_metric",
    "cl-009-3": "absence",
    "cl-011-3": "absence",
    "cl-014-3": "absence",
    "cl-015-1": "arithmetic",
    "cl-015-2": "arithmetic",
    "cl-016-1": "temporal_boundary",
    "cl-018-1": "fragment",
    "cl-018-2": "fragment",
    "cl-024-1": "comparison",
    "cl-027-2": "author_ai_disagreement",
    "cl-029-1": "scope_equivalence",
    "cl-031-2": "arithmetic",
    "cl-032-1": "temporal_boundary",
}

PROMPT = """\
Protocol prompt claimledger.inference_prompt.v1

You will receive one JSON object with evaluation_id, claim, and passage.
Decide from that passage alone.
Return one JSON object and nothing else, using the same evaluation_id.
The verdict field must be supported, contradicted, or insufficient.
Use supported only when the passage establishes the whole claim.
Use contradicted only when the passage establishes that the claim is false.
Use insufficient when the passage does not settle the claim.
The quote must be an exact substring of the passage. Leave quote empty for insufficient.
Do not read any other file, identifier, or note.
"""

ISOLATED_README = """\
# Model-visible evaluation view

This directory is the only input an evaluator may read.
Do not open the repository, the audit mapping, the review queue, or the AI annotation files.
inputs.jsonl has one JSON object per line: evaluation_id, claim, passage_id, and passage.
prompt.txt is the instruction.
Copying this directory outside the repository only copies these files.
That copy is not an operating-system sandbox.
The audit mapping committed in the repository is publicly readable.
This view is an internal export. It is not an independent external test set.
No score file belongs here.
"""

BOUNDARY = """\
Agent boundary

Read only the files in this directory.
Do not access a ClaimLedger checkout, an answer key, a mapping file, or a score file.
Copying these files to another folder is not an operating-system sandbox.
A process that can open other paths can still read the repository.
"""

HUMAN_README = """\
# Human calibration packet

This directory is a 30-case calibration subset.
Two reviewers work independently.
Reviewer A receives response_sheet_A.csv. Reviewer B receives response_sheet_B.csv.
Give each person this packet and only that person's sheet.
Do not give them the repository, author labels, or AI notes.

A review label is one of: supported, contradicted, insufficient.
Leave the label blank until you decide.
Write an evidence quote only as an exact substring of the passage, plus its character span.
Do not mark the canonical queue reviewed from this sheet.
The adjudication log stays empty until both reviews exist.
This packet is not an independent external test and it does not release a gold set.
"""

ISOLATED_FILES = ("README.md", "BOUNDARY.txt", "prompt.txt", "inputs.jsonl")
HUMAN_FILES = (
    "README.md",
    "calibration_packet.jsonl",
    "response_sheet_A.csv",
    "response_sheet_B.csv",
    "adjudication_log.csv",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def permitted_passage(text: str) -> str:
    """Drop the scenario heading. Its number is the canonical document number."""
    lines = text.splitlines()
    if not lines or SCENARIO_HEADING_RE.fullmatch(lines[0]) is None:
        raise ValueError("Refusing a source whose first line is not the scenario heading.")
    body = "\n".join(lines[1:]).strip()
    if not body:
        raise ValueError("Passage is empty after removing the scenario heading.")
    if "Fictional scenario" in body or CANONICAL_ID_RE.search(body) or DOCUMENT_NAME_RE.search(body):
        raise ValueError("Passage still carries a canonical identifier.")
    return body + "\n"


def load_canonical_cases(candidates: Path) -> list[dict]:
    manifest = json.loads((candidates / "manifest.json").read_text(encoding="utf-8"))
    cases = []
    with (candidates / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            document = row["document"]
            source = (candidates / document).resolve()
            if not source.is_relative_to(candidates.resolve()) or not source.is_file():
                raise ValueError(f"Document path escapes the candidate set: {document}")
            raw = source.read_bytes()
            digest = _sha256(raw)
            filename = Path(document).name
            if manifest["document_sha256"][filename] != digest:
                raise ValueError(f"Stale manifest hash for {filename}.")
            cases.append({
                "canonical_id": row["id"],
                "claim": row["claim"],
                "author_label": row["expected"],
                "reviewed_label": row["reviewed_label"],
                "human_reviewed": row["human_reviewed"],
                "document": document,
                "document_sha256": digest,
                "passage": permitted_passage(raw.decode("utf-8")),
            })
    if len(cases) != manifest["rows"]:
        raise ValueError("Review queue count does not match the manifest.")
    return cases


def _bad_order(items: list[dict]) -> bool:
    documents = [item["document"] for item in items]
    if any(documents[i] == documents[i + 1] == documents[i + 2] for i in range(len(documents) - 2)):
        return True
    cycle = CLASSES
    labels = [item["author_label"] for item in items]
    if labels == [cycle[i % 3] for i in range(len(labels))]:
        return True
    grouped: dict[str, list[str]] = {}
    for item in items:
        grouped.setdefault(item["document"], []).append(item["canonical_id"])
    return any(len(ids) >= 2 and ids == sorted(ids) for ids in grouped.values())


def _token(rng: random.Random, prefix: str, seen: set[str]) -> str:
    for _ in range(1000):
        value = f"{prefix}{rng.getrandbits(48):012x}"
        if value not in seen:
            seen.add(value)
            return value
    raise RuntimeError(f"Could not draw a unique {prefix} id.")


def blinded_order(cases: list[dict], seed: int) -> tuple[list[dict], int]:
    """Shuffle every case once, across documents, rejecting label-bearing orders."""
    rng = random.Random(seed)
    items = list(cases)
    rejected = 0
    while True:
        rng.shuffle(items)
        if not _bad_order(items):
            return items, rejected
        rejected += 1
        if rejected > MAX_SHUFFLE_DRAWS:
            raise RuntimeError("No label-blind order for this seed.")


def _assign_public_ids(ordered: list[dict], rng: random.Random) -> list[dict]:
    seen: set[str] = set()
    passage_ids: dict[str, str] = {}
    rows = []
    for item in ordered:
        if item["document"] not in passage_ids:
            passage_ids[item["document"]] = _token(rng, "p-", seen)
        rows.append({
            **item,
            "evaluation_id": _token(rng, "ev-", seen),
            "passage_id": passage_ids[item["document"]],
        })
    return rows


def _flag_ids(candidates: Path) -> set[str]:
    with (candidates / "pre_review_flags.csv").open(encoding="utf-8", newline="") as handle:
        return {row["id"] for row in csv.DictReader(handle)}


def select_calibration(cases: list[dict], flag_ids: set[str]) -> list[dict]:
    """Thirty cases: every pre-review flag, then the lowest ids needed for balance."""
    flagged = sorted(
        (case for case in cases if case["canonical_id"] in flag_ids),
        key=lambda case: case["canonical_id"],
    )
    if len(flagged) != len(flag_ids):
        raise ValueError("A pre-review flag does not match a canonical case.")
    counts = {label: sum(case["author_label"] == label for case in flagged) for label in CLASSES}
    chosen = list(flagged)
    roles = {case["canonical_id"]: "pre_review_flag" for case in flagged}
    for label in CLASSES:
        need = CALIBRATION_PER_CLASS - counts[label]
        if need < 0:
            raise ValueError(f"Pre-review flags exceed {CALIBRATION_PER_CLASS} {label} cases.")
        pool = sorted(
            (
                case for case in cases
                if case["author_label"] == label and case["canonical_id"] not in flag_ids
            ),
            key=lambda case: case["canonical_id"],
        )
        if len(pool) < need:
            raise ValueError(f"Not enough {label} cases to fill the calibration subset.")
        for case in pool[:need]:
            chosen.append(case)
            roles[case["canonical_id"]] = "class_balance"
    if len(chosen) != CALIBRATION_PER_CLASS * len(CLASSES):
        raise ValueError("Calibration subset is not 30 cases.")
    for case in chosen:
        role = roles[case["canonical_id"]]
        case["calibration_role"] = role
        fallback = "class_balance" if role == "class_balance" else "pre_review_flag"
        case["calibration_category"] = FLAG_CATEGORIES.get(case["canonical_id"], fallback)
    return chosen


def inter_annotator_agreement(rows: list[dict]) -> dict:
    """Score filled slots. Never treat a filled sheet as a human-reviewed gold row."""
    by_case: dict[str, dict[str, str]] = {}
    for row in rows:
        label = (row.get("reviewed_label") or "").strip()
        if not label:
            continue
        by_case.setdefault(row["packet_id"], {})[row["reviewer_slot"]] = label
    disagreements = []
    paired = 0
    for packet_id, slots in sorted(by_case.items()):
        if "A" not in slots or "B" not in slots:
            continue
        paired += 1
        if slots["A"] != slots["B"]:
            disagreements.append({
                "packet_id": packet_id,
                "reviewer_a_label": slots["A"],
                "reviewer_b_label": slots["B"],
            })
    raw = None if paired == 0 else (paired - len(disagreements)) / paired
    return {
        "paired_cases": paired,
        "agreements": paired - len(disagreements),
        "disagreements": disagreements,
        "raw_agreement": raw,
        "human_reviewed_rows": 0,
    }


def reconcile(predictions: list[dict], mapping: dict) -> list[dict]:
    """Join model verdicts to canonical cases. The mapping is the only join key."""
    if not mapping or "cases" not in mapping:
        raise ValueError("Reconciliation requires the audit mapping.")
    index = {row["evaluation_id"]: row for row in mapping["cases"]}
    resolved = []
    for prediction in predictions:
        leaked = FORBIDDEN_RECORD_KEYS.intersection(prediction)
        if leaked:
            raise ValueError(f"A model output includes answer-key fields: {sorted(leaked)}")
        evaluation_id = prediction["evaluation_id"]
        if evaluation_id not in index:
            raise ValueError("Unknown evaluation id. The audit mapping is required.")
        verdict = prediction["verdict"]
        if verdict not in CLASSES:
            raise ValueError("Verdict is not one of the three classes.")
        source = index[evaluation_id]
        resolved.append({
            "canonical_id": source["canonical_id"],
            "author_label": source["author_label"],
            "verdict": verdict,
        })
    return resolved


def _response_sheet(packet_rows: list[dict], slot: str) -> str:
    fieldnames = [
        "packet_id", "reviewer_slot", "reviewer_id", "reviewed_at", "reviewed_label",
        "evidence_start", "evidence_end", "evidence_quote", "notes",
    ]
    lines = [",".join(fieldnames)]
    for row in packet_rows:
        lines.append(",".join([row["packet_id"], slot, "", "", "", "", "", "", ""]))
    return "\n".join(lines) + "\n"


def _adjudication_header() -> str:
    return (
        "packet_id,reviewer_a_label,reviewer_b_label,labels_agree,"
        "adjudicated_label,adjudicator,adjudicated_at,notes\n"
    )


def build_bundle(candidates: Path) -> dict:
    cases = load_canonical_cases(candidates)
    ordered, rejected = blinded_order(cases, SEED)
    public_rows = _assign_public_ids(ordered, random.Random(EVALUATION_ID_SEED))
    inputs = [{
        "evaluation_id": row["evaluation_id"],
        "claim": row["claim"],
        "passage_id": row["passage_id"],
        "passage": row["passage"],
    } for row in public_rows]
    mapping_cases = [{
        "evaluation_id": row["evaluation_id"],
        "canonical_id": row["canonical_id"],
        "author_label": row["author_label"],
        "document": row["document"],
        "document_sha256": row["document_sha256"],
        "passage_id": row["passage_id"],
        "passage_sha256": _sha256(row["passage"].encode("utf-8")),
    } for row in public_rows]

    flagged = _flag_ids(candidates)
    selected = select_calibration(cases, flagged)
    human_rng = random.Random(HUMAN_PACKET_SEED)
    human_rng.shuffle(selected)
    seen: set[str] = set()
    packet_source = []
    for case in selected:
        packet_source.append({**case, "packet_id": _token(human_rng, "hr-", seen)})
    passage_ids: dict[str, str] = {}
    packet = []
    for row in packet_source:
        if row["document"] not in passage_ids:
            passage_ids[row["document"]] = _token(human_rng, "hp-", seen)
        packet.append({
            "packet_id": row["packet_id"],
            "claim": row["claim"],
            "passage_id": passage_ids[row["document"]],
            "passage": row["passage"],
        })
    calibration_cases = [{
        "packet_id": row["packet_id"],
        "canonical_id": row["canonical_id"],
        "author_label": row["author_label"],
        "category": row["calibration_category"],
        "role": row["calibration_role"],
        "document_sha256": row["document_sha256"],
    } for row in packet_source]

    inputs_text = _jsonl(inputs)
    prompt_text = PROMPT
    manifest = json.loads((candidates / "manifest.json").read_text(encoding="utf-8"))
    protocol = {
        "protocol_version": PROTOCOL_VERSION,
        "prompt_version": PROMPT_VERSION,
        "randomization_seed": SEED,
        "evaluation_id_seed": EVALUATION_ID_SEED,
        "human_packet_seed": HUMAN_PACKET_SEED,
        "rng": "CPython random.Random",
        "rejected_shuffles": rejected,
        "dataset_version": manifest["dataset_version"],
        "canonical_rows": len(cases),
        "isolated_rows": len(inputs),
        "calibration_rows": len(packet),
        "heading_redaction": (
            "Model-visible passages omit the leading '# Fictional scenario NNN' line "
            "because that number is the canonical document number."
        ),
        "model_visible_directory": "benchmark/evaluation/isolated",
        "audit_mapping": "benchmark/evaluation/audit/id_mapping.json",
        "audit_mapping_access": "committed_in_the_public_repository",
        "audit_mapping_is_access_controlled": False,
        "agent_directory_is_os_sandbox": False,
        "agent_rule": (
            "The committed audit mapping is publicly readable. It is separate from the "
            "model-visible directory, and it is not access-controlled. Copying that "
            "directory outside the repository is a file copy, not an operating-system sandbox."
        ),
        "evaluator": {
            "configured": False,
            "backend": None,
            "model": None,
            "paid_inference": False,
            "runs_completed": 0,
        },
        "creates_external_blind_test": False,
        "result_classes": {
            "synthetic_author_label_smoke": (
                "Local exact-match scores on author labels. Not a blinded semantic evaluation."
            ),
            "ai_second_opinion": (
                "Annotations under benchmark/candidates/ai_second_opinion. "
                "Not human review and not an accuracy estimate."
            ),
            "human_reviewed_development": (
                "The 30-case calibration packet has no recorded decisions."
            ),
            "internal_label_blinded_test": (
                "The isolated export exists. No blinded model run has been scored."
            ),
            "independent_external_test": (
                "Not available. This protocol does not create an external test set."
            ),
        },
        "isolated_inputs_sha256": _sha256(inputs_text.encode("utf-8")),
        "prompt_sha256": _sha256(prompt_text.encode("utf-8")),
        "review_queue_sha256": _sha256((candidates / "review_queue.csv").read_bytes()),
    }
    file_hashes = {
        "benchmark/candidates/review_queue.csv": protocol["review_queue_sha256"],
        "benchmark/candidates/manifest.json": _sha256((candidates / "manifest.json").read_bytes()),
        "benchmark/candidates/split.json": _sha256((candidates / "split.json").read_bytes()),
        "benchmark/candidates/pre_review_flags.csv": _sha256(
            (candidates / "pre_review_flags.csv").read_bytes()
        ),
    }
    for name, digest in sorted(manifest["document_sha256"].items()):
        file_hashes[f"benchmark/candidates/documents/{name}"] = digest
    return {
        "protocol": protocol,
        "mapping": {
            "protocol_version": PROTOCOL_VERSION,
            "randomization_seed": SEED,
            "cases": mapping_cases,
        },
        "calibration_mapping": {
            "protocol_version": PROTOCOL_VERSION,
            "human_packet_seed": HUMAN_PACKET_SEED,
            "cases": calibration_cases,
        },
        "dataset_hashes": {
            "protocol_version": PROTOCOL_VERSION,
            "dataset_version": manifest["dataset_version"],
            "files": file_hashes,
        },
        "isolated": {
            "README.md": ISOLATED_README,
            "BOUNDARY.txt": BOUNDARY,
            "prompt.txt": prompt_text,
            "inputs.jsonl": inputs_text,
        },
        "human": {
            "README.md": HUMAN_README,
            "calibration_packet.jsonl": _jsonl(packet),
            "response_sheet_A.csv": _response_sheet(packet, "A"),
            "response_sheet_B.csv": _response_sheet(packet, "B"),
            "adjudication_log.csv": _adjudication_header(),
        },
        "public_rows": public_rows,
        "rejected_shuffles": rejected,
    }


def rendered_files(bundle: dict) -> dict[str, str]:
    files = {
        "benchmark/evaluation/audit/protocol.json": _dump(bundle["protocol"]),
        "benchmark/evaluation/audit/id_mapping.json": _dump(bundle["mapping"]),
        "benchmark/evaluation/audit/calibration_mapping.json": _dump(bundle["calibration_mapping"]),
        "benchmark/evaluation/audit/dataset_hashes.json": _dump(bundle["dataset_hashes"]),
    }
    for name, text in bundle["isolated"].items():
        files[f"benchmark/evaluation/isolated/{name}"] = text
    for name, text in bundle["human"].items():
        files[f"benchmark/evaluation/human_review/{name}"] = text
    return files


def assert_text_has_no_answer_key(text: str, *, allow_label_words: bool) -> None:
    if CANONICAL_ID_RE.search(text) or DOCUMENT_NAME_RE.search(text):
        raise ValueError("Model-visible text contains a canonical case id or document name.")
    if "Fictional scenario" in text:
        raise ValueError("Model-visible text contains a scenario heading.")
    if not allow_label_words and LABEL_WORD_RE.search(text):
        raise ValueError("Model-visible text contains a class label.")
    for key in ("author_label", "ai_verdict", "canonical_id", "expected", "human_reviewed"):
        if key in text:
            raise ValueError(f"Model-visible text contains {key}.")


def assert_isolated_tree(directory: Path) -> None:
    present = {path.name for path in directory.iterdir() if path.is_file()}
    if present != set(ISOLATED_FILES) or any(path.is_dir() for path in directory.iterdir()):
        raise ValueError("The isolated directory has files other than the model view.")
    for path in directory.iterdir():
        allow = path.name == "prompt.txt"
        assert_text_has_no_answer_key(path.read_text(encoding="utf-8"), allow_label_words=allow)
        for record in _json_records(path):
            leaked = FORBIDDEN_RECORD_KEYS.intersection(record)
            if leaked:
                raise ValueError(f"Model-visible record has answer-key fields: {sorted(leaked)}")


def assert_human_tree(directory: Path) -> None:
    present = {path.name for path in directory.iterdir() if path.is_file()}
    if present != set(HUMAN_FILES) or any(path.is_dir() for path in directory.iterdir()):
        raise ValueError("The human-review directory has unexpected files.")
    for path in directory.iterdir():
        allow = path.name == "README.md"
        assert_text_has_no_answer_key(path.read_text(encoding="utf-8"), allow_label_words=allow)


def _json_records(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else [payload]
    return []


def prepare_agent_view(destination: Path, repo_root: Path, bundle: dict) -> None:
    """Copy only the model view. This is a file copy, not an operating-system sandbox."""
    dest = destination.resolve()
    root = repo_root.resolve()
    if dest == root or dest.is_relative_to(root):
        raise ValueError("The agent directory must be outside the repository.")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("The agent directory must start empty.")
    dest.mkdir(parents=True, exist_ok=True)
    for name, text in bundle["isolated"].items():
        (dest / name).write_text(text, encoding="utf-8", newline="\n")
    assert_isolated_tree(dest)


def write_bundle(repo_root: Path, bundle: dict) -> None:
    for relative, text in rendered_files(bundle).items():
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def committed_files_match(repo_root: Path, bundle: dict) -> bool:
    for relative, text in rendered_files(bundle).items():
        path = repo_root / relative
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            return False
    return True
