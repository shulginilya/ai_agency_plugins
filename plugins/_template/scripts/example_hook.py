#!/usr/bin/env python3
"""A lifecycle hook. Reads the event JSON on stdin; must always exit 0.

A hook that fails a valid action is worse than no hook at all: it blocks work
the user asked for, and the failure is hard to attribute. Swallow every error.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0
    # Inspect event["tool_input"], print a note on stdout when it matters.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
