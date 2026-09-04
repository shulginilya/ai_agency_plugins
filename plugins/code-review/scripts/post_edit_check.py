#!/usr/bin/env python3
"""PostToolUse hook: flag debris in a file that was just written or edited.

Reads the hook event JSON on stdin, looks at the file the tool touched, and
prints a short note when it finds something a reviewer would reject. It never
blocks: exit status is always 0, and an unreadable or unrecognised event is
simply ignored. A hook that fails a valid edit is worse than no hook.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_BYTES = 512_000

CODE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rb", ".java"}

PATTERNS = [
    (re.compile(r"^\s*(console\.log|console\.debug)\(", re.M), "left-over console logging"),
    (re.compile(r"^\s*debugger\s*;?\s*$", re.M), "a `debugger` statement"),
    (re.compile(r"^\s*(it|test|describe)\.only\(", re.M), "a focused test (`.only`) that will hide the rest of the suite"),
    (re.compile(r"\b(eslint-disable|@ts-ignore|# noqa)\b"), "a suppressed lint or type error"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"), "what looks like a hard-coded credential"),
    (re.compile(r"(?i)\bTODO\b.*\b(security|auth|fix before|prod)\b"), "a TODO that says it must not ship"),
]


def target_path(event: dict) -> Path | None:
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("filePath")
    if not raw:
        return None
    path = Path(str(raw))
    return path if path.suffix in CODE_SUFFIXES else None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0

    path = target_path(event)
    if path is None or not path.is_file():
        return 0
    try:
        if path.stat().st_size > MAX_BYTES:
            return 0
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    hits = [label for pattern, label in PATTERNS if pattern.search(text)]
    if hits:
        print("code-review: %s contains %s." % (path.name, "; ".join(hits)))
        print("Clean it up before this reaches review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
