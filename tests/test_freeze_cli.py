import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _queue(path: Path, reviewed: bool) -> None:
    note = path.parent / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    reviewed_label = "supported" if reviewed else ""
    reviewer = "ada" if reviewed else ""
    reviewed_at = "2026-10-17" if reviewed else ""
    flag = "True" if reviewed else "False"
    path.write_text(
        "id,scenario,category,document,claim,expected,reviewed_label,evidence_quote,"
        "label_origin,human_reviewed,reviewer,reviewed_at,review_notes\n"
        "cl-901-1,901,numeric,note.md,The sample count is 4.,supported,"
        f"{reviewed_label},The sample count is 4.,synthetic_author_labeled,"
        f"{flag},{reviewer},{reviewed_at},\n",
        encoding="utf-8",
    )


def _run(queue: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/freeze_reviewed_labels.py",
         "--queue", str(queue), "--out", str(out),
         "--dataset-version", "candidates-test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_freeze_cli_with_zero_reviewed_cases(tmp_path: Path):
    queue = tmp_path / "review_queue.csv"
    out = tmp_path / "frozen.json"
    _queue(queue, reviewed=False)
    completed = _run(queue, out)
    assert completed.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["reviewed_case_count"] == 0
    assert payload["reviewed_subset_available"] is False
    assert payload["eligible_for_final_approval"] is False
    assert payload["gold_benchmark_released"] is False
    assert "human_reviewed" not in completed.stdout


def test_freeze_cli_with_one_reviewed_case(tmp_path: Path):
    queue = tmp_path / "review_queue.csv"
    out = tmp_path / "frozen.json"
    _queue(queue, reviewed=True)
    completed = _run(queue, out)
    assert completed.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["reviewed_case_count"] == 1
    assert payload["reviewed_subset_available"] is True
    assert payload["eligible_for_final_approval"] is False
    assert payload["gold_benchmark_released"] is False
    assert payload["cases"][0]["author_label"] == "supported"
    assert payload["independence_verified"] is False
