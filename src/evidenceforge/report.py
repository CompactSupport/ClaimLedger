from __future__ import annotations

from typing import Any


def _safe_md(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")


def markdown_report(report: dict[str, Any]) -> str:
    lines = ["# EvidenceForge verification report", "",
             f"Backend: `{report['backend']}`; documents: {len(report['documents'])}; claims: {len(report['results'])}",
             "", "| Claim | Verdict |", "|---|---|"]
    for result in report["results"]:
        lines.append(f"| {_safe_md(result['claim'])} | **{result['verdict']}** |")
    for result in report["results"]:
        lines += ["", f"## {result['id']}: {_safe_md(result['claim'])}", "",
                  f"**Verdict:** `{result['verdict']}`", "",
                  f"**Reason:** {_safe_md(result['reason'])}", ""]
        if not result["evidence"]:
            lines += ["No validated source quote.", ""]
        for quote in result["evidence"]:
            location = (f"{_safe_md(quote['source'])}, page {quote['page']}, "
                        f"extracted-text chars [{quote['start']}, {quote['end']})")
            lines += [f"- **{location}**: `{_safe_md(quote['quote'])}`"]
        if result["audit_warnings"]:
            lines += ["", "Audit warnings:"]
            lines.extend(f"- {_safe_md(w)}" for w in result["audit_warnings"])
    lines += ["", "---", "", f"**Important:** {report['disclaimer']}", ""]
    return "\n".join(lines)
