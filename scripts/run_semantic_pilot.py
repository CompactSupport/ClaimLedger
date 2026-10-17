#!/usr/bin/env python3
"""Report the semantic-pilot gate. This command does not launch a model."""

from __future__ import annotations


def main() -> int:
    print("real_codex_inference=disabled")
    print("api_key_fallback=refused")
    print("os_sandbox=false")
    print("predictions_are_human_labels=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
