from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .ingest import load_pages
from .metrics import citation_counts, classification_metrics
from .pipeline import verify_documents
from .report import markdown_report


def read_claims(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("claims")
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise ValueError('Claims JSON must be a list of strings or {"claims": ["..."]}.')
    return data


def write_output(path: str | None, contents: str) -> None:
    if path:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        print(f"Wrote {dest}", file=sys.stderr)
    else:
        print(contents)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimledger", description="Traceable claim verification")
    sub = parser.add_subparsers(dest="command", required=True)
    ver = sub.add_parser("verify", help="Verify supplied claims against supplied documents")
    ver.add_argument("--doc", action="append", required=True, help=".md, .txt or .pdf; repeatable")
    ver.add_argument("--claims", required=True, type=Path, help="JSON array of claim strings")
    ver.add_argument("--backend", choices=["local", "openai"], default="local")
    ver.add_argument("--model", default="gpt-5-mini")
    ver.add_argument("--top-k", type=int, default=5,
                     help="Passages sent to OpenAI. Local mode still scans every chunk.")
    ver.add_argument("--out", help="Output JSON path, otherwise stdout")
    ver.add_argument("--markdown", help="Optional Markdown report path")

    ev = sub.add_parser("evaluate", help="Evaluate labeled JSONL examples against a verifier")
    ev.add_argument("--dataset", type=Path, required=True)
    ev.add_argument("--backend", choices=["local", "openai"], default="local")
    ev.add_argument("--model", default="gpt-5-mini")
    ev.add_argument("--out", help="Evaluation JSON path, otherwise stdout")
    return parser


def evaluate_dataset(path: Path, backend: str, model: str) -> dict:
    examples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    if not examples or len(examples) > 30:
        raise ValueError("Dataset must contain 1 to 30 examples per evaluation run.")
    cases = []
    confusion: dict[str, dict[str, int]] = {}
    tokens = 0
    valid_quotes = 0
    total_quotes = 0
    started = time.perf_counter()
    for i, case in enumerate(examples):
        expected = case["expected"]
        if expected not in {"supported", "contradicted", "insufficient"}:
            raise ValueError(f"Invalid expected verdict on line {i+1}")
        source = (path.parent / case["document"]).resolve()
        # Limit dataset paths to files inside the dataset directory.
        if not source.is_relative_to(path.parent.resolve()):
            raise ValueError("Dataset document paths must remain inside the dataset directory.")
        pages = load_pages([source])
        report = verify_documents([source], [case["claim"]], backend=backend, model=model)
        valid, total = citation_counts(pages, report["results"])
        valid_quotes += valid
        total_quotes += total
        actual = report["results"][0]["verdict"]
        confusion.setdefault(expected, {}).setdefault(actual, 0)
        confusion[expected][actual] += 1
        tokens += report["token_usage"]["total_tokens"]
        cases.append({"claim": case["claim"], "expected": expected, "actual": actual,
                      "pass": actual == expected})
    pairs = [(case["expected"], case["actual"]) for case in cases]
    metrics = classification_metrics(pairs)
    abstain_metrics = classification_metrics([(expected, "insufficient") for expected, _ in pairs])
    return {
        "total": len(cases),
        "correct": sum(case["pass"] for case in cases),
        "accuracy": sum(case["pass"] for case in cases) / len(cases),
        "confusion": confusion,
        "total_tokens": tokens,
        "backend": backend,
        "model": model if backend == "openai" else None,
        "cases": cases,
        "dataset_tier": "smoke",
        "dataset_label_origin": "synthetic_author_labeled",
        "gold_benchmark": False,
        "metrics": metrics,
        "baselines": {
            backend: metrics,
            "abstain": abstain_metrics,
        },
        "citation_validity_rate": valid_quotes / total_quotes if total_quotes else None,
        "retrieval_recall": None,
        "latency_seconds": time.perf_counter() - started,
        "warning": (
            "This is a small synthetic smoke fixture, not a human-reviewed gold benchmark. "
            "retrieval_recall is null because rows do not name a relevant evidence unit."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            report = verify_documents(args.doc, read_claims(args.claims),
                                      backend=args.backend, model=args.model, top_k=args.top_k)
            write_output(args.out, json.dumps(report, indent=2, ensure_ascii=False))
            if args.markdown:
                write_output(args.markdown, markdown_report(report))
            if args.out:
                summary = report["verdict_counts"]
                print(f"Results: {summary}; tokens: {report['token_usage']['total_tokens']}", file=sys.stderr)
        else:
            result = evaluate_dataset(args.dataset, args.backend, args.model)
            write_output(args.out, json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
