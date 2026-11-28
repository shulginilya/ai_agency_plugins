#!/usr/bin/env python3
"""Find every reference to a symbol, so a refactor's blast radius is known
before the first edit rather than after the first broken build.

Hits are grouped: where the symbol is defined, which call sites are production
code, and which are tests. Tests matter separately — they are the harness that
proves the refactor preserved behaviour, and they are also call sites that have
to move with it.

Usage:
    python scripts/callers.py parseConfig
    python scripts/callers.py UserRepository --root src --json
    python scripts/callers.py send_email --ext .py

Exits 0 whether or not anything was found (an unused symbol is a real answer),
and 2 when the root is not a directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", "target", "vendor",
    "__pycache__", ".venv", "venv", ".next", ".tox", "coverage", ".mypy_cache",
}
CODE_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rb", ".rs",
    ".java", ".kt", ".cs", ".php", ".swift", ".scala", ".sql", ".vue", ".svelte",
}
TEST_HINTS = ("test", "spec", "__tests__", "e2e", "fixtures")
MAX_BYTES = 2_000_000

DEFINITION_KEYWORDS = (
    "def", "class", "function", "const", "let", "var", "type", "interface",
    "enum", "struct", "trait", "impl", "func", "fn", "async function",
)


def _is_test(path: Path) -> bool:
    lowered = str(path).lower().replace("\\", "/")
    return any(hint in lowered for hint in TEST_HINTS)


def _definition_re(symbol: str) -> re.Pattern:
    keywords = "|".join(DEFINITION_KEYWORDS)
    return re.compile(
        r"(?:\b(?:%s)\s+%s\b)|(?:\b%s\s*[:=]\s*(?:async\s+)?(?:function\b|\(|class\b))"
        % (keywords, re.escape(symbol), re.escape(symbol))
    )


def scan(root: Path, symbol: str, suffixes: List[str]) -> List[Dict[str, object]]:
    word = re.compile(r"\b%s\b" % re.escape(symbol))
    definition = _definition_re(symbol)
    wanted = set(suffixes) if suffixes else CODE_SUFFIXES
    hits: List[Dict[str, object]] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in wanted:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if symbol not in text:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if not word.search(line):
                continue
            hits.append(
                {
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "line": number,
                    "text": line.strip()[:160],
                    "kind": "definition" if definition.search(line) else "reference",
                    "test": _is_test(path),
                }
            )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help="function, class, constant or type name")
    parser.add_argument("--root", default=".", help="directory to search (default: cwd)")
    parser.add_argument("--ext", action="append", default=[], help="restrict to a suffix, e.g. --ext .py")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write("not a directory: %s\n" % root)
        return 2

    hits = scan(root, args.symbol, args.ext)

    if args.json:
        print(json.dumps(hits, indent=2))
        return 0

    if not hits:
        print("no references to %r under %s" % (args.symbol, root))
        return 0

    groups = [
        ("definitions", [h for h in hits if h["kind"] == "definition"]),
        ("call sites", [h for h in hits if h["kind"] == "reference" and not h["test"]]),
        ("tests", [h for h in hits if h["kind"] == "reference" and h["test"]]),
    ]
    files = len({h["path"] for h in hits})
    print("%d reference(s) to %r across %d file(s)" % (len(hits), args.symbol, files))
    for label, entries in groups:
        if not entries:
            continue
        print("\n%s (%d)" % (label, len(entries)))
        for hit in entries:
            print("  %s:%s  %s" % (hit["path"], hit["line"], hit["text"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
