#!/usr/bin/env python3
"""Detect fixes that hide a symptom instead of removing its cause.

Usage:
    python scripts/suppression.py src/cart/total.ts
    python scripts/suppression.py --json src/**/*.py

This is the single home for the rule. The plugin's PostToolUse hook imports
`scan` from here rather than restating the patterns, so there is one list to
correct when a pattern turns out to be noisy.

Each pattern is deliberately narrow. A check that fires on ordinary code gets
ignored, and an ignored check is worse than none: the whole point is that the
one time it fires, someone reads it.

Exits 0 whether or not anything was found — this reports, it does not gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

CODE_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".py", ".go", ".rb", ".java", ".kt", ".cs", ".php", ".rs", ".swift",
}

PATTERNS: List[Tuple["re.Pattern[str]", str]] = [
    (
        re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}"),
        "an empty catch block — the failure is swallowed, not handled",
    ),
    (
        re.compile(r"\.catch\(\s*(?:\(\s*[^)]*\)|\w+)\s*=>\s*\{\s*\}\s*\)"),
        "a rejection handler that does nothing",
    ),
    (
        re.compile(
            r"(?m)^[ \t]*except\b[^\n:]*:[ \t]*"
            r"(?:(?:pass|\.\.\.)[ \t]*$|\r?\n[ \t]+(?:pass|\.\.\.)[ \t]*$)"
        ),
        "an `except` that passes — the failure is swallowed",
    ),
    (
        re.compile(r"(?m)^[ \t]*_\s*(?::=|=)\s*err\b"),
        "an error assigned to `_` — the failure is discarded",
    ),
    (
        re.compile(r"(?m)^[ \t]*rescue\b[^\n]*\n[ \t]*end\b"),
        "an empty `rescue` — the failure is swallowed",
    ),
    (
        re.compile(r"@ts-ignore|@ts-nocheck|eslint-disable|#\s*noqa|#\s*type:\s*ignore|//\s*nolint"),
        "a suppressed type or lint error",
    ),
    (
        re.compile(r"(?m)^[ \t]*(?:(?:it|test|describe)\.skip\(|x(?:it|describe)\(|@pytest\.mark\.skip|t\.Skip\(\))"),
        "a skipped test — if it caught the bug, skipping it is not the fix",
    ),
    (
        re.compile(r"\bas\s+unknown\s+as\b|\bas\s+any\b|:\s*any\b"),
        "a cast to `any` that hides the real shape of the value",
    ),
    (
        re.compile(r"(?i)//\s*(?:TODO|FIXME|HACK)\b[^\n]*\b(?:temporar|workaround|for now|revisit)"),
        "a workaround marked as temporary",
    ),
]


def scan(text: str) -> List[str]:
    """Return the labels of every suppression pattern present in text."""
    return [label for pattern, label in PATTERNS if pattern.search(text)]


def is_code(path: Path) -> bool:
    return path.suffix in CODE_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="files to check")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    findings = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file() or not is_code(path):
            continue
        try:
            hits = scan(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if hits:
            findings.append({"path": str(path), "found": hits})

    if args.json:
        print(json.dumps(findings, indent=2))
        return 0
    for finding in findings:
        print("%s: %s" % (finding["path"], "; ".join(finding["found"])))
    if not findings:
        print("no symptom suppression found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
