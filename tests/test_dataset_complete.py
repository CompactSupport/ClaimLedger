import json
from pathlib import Path

import pytest

from claimledger.candidates import assert_dataset_complete


def _manifest(rows: int = 1) -> dict:
    return {
        "shards": 1,
        "rows": rows,
        "dataset_version": "candidates-test",
        "labels": {"supported": rows, "contradicted": 0, "insufficient": 0},
        "document_sha256": {"note.md": ""},
    }


def _write(base: Path, text: str = "hello\n") -> str:
    source = base / "documents"
    source.mkdir()
    file = source / "note.md"
    file.write_text(text, encoding="utf-8")
    import hashlib
    return hashlib.sha256(file.read_bytes()).hexdigest()


def _row(case_id: str = "cl-001-1") -> dict:
    return {
        "id": case_id,
        "document": "documents/note.md",
        "claim": "hello",
        "expected": "supported",
    }


def test_complete_dataset_is_accepted(tmp_path: Path):
    digest = _write(tmp_path)
    manifest = _manifest()
    manifest["document_sha256"]["note.md"] = digest
    row = _row()
    assert_dataset_complete([[row]], [row], manifest, tmp_path)


def test_missing_shard_is_rejected(tmp_path: Path):
    digest = _write(tmp_path)
    manifest = _manifest()
    manifest["shards"] = 2
    manifest["document_sha256"]["note.md"] = digest
    with pytest.raises(ValueError, match="Shard count"):
        assert_dataset_complete([[_row()]], [_row()], manifest, tmp_path)


def test_duplicate_and_unexpected_rows_are_rejected(tmp_path: Path):
    digest = _write(tmp_path)
    manifest = _manifest(rows=2)
    manifest["labels"]["supported"] = 2
    manifest["document_sha256"]["note.md"] = digest
    row = _row()
    other = _row("cl-001-2")
    other["claim"] = "other"
    with pytest.raises(ValueError, match="duplicated"):
        assert_dataset_complete([[row, row]], [row, row], manifest, tmp_path)
    single = _manifest(rows=1)
    single["document_sha256"]["note.md"] = digest
    with pytest.raises(ValueError, match="do not match"):
        assert_dataset_complete([[other]], [_row()], single, tmp_path)


def test_stale_manifest_hash_is_rejected(tmp_path: Path):
    _write(tmp_path)
    manifest = _manifest()
    manifest["document_sha256"]["note.md"] = "0" * 64
    with pytest.raises(ValueError, match="Stale manifest"):
        assert_dataset_complete([[_row()]], [_row()], manifest, tmp_path)


def test_manifest_round_trip(tmp_path: Path):
    path = tmp_path / "manifest.json"
    payload = {"dataset_version": "candidates-test", "rows": 108}
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["rows"] == 108
